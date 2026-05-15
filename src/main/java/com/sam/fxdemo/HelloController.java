package com.sam.fxdemo;

import javafx.beans.property.ReadOnlyStringWrapper;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.stage.FileChooser;
import com.sam.fxdemo.api.FastApiClient;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

// Controls the CSV table screen and loads rows from a user-selected CSV file.
public class HelloController {
    private final FastApiClient fastApiClient = new FastApiClient();

    // Lets the user choose a CSV file from their computer.
    @FXML
    private Button uploadButton;

//    @FXML
//    private Button apiStatusButton;

    // Displays a short count/status message above the table.
    @FXML
    private Label statusLabel;

    @FXML
    private Label apiStatusLabel;

    // Shows the CSV content using dynamically created columns.
    @FXML
    private TableView<ObservableList<String>> csvTable;

    // Runs automatically after the FXML is loaded.
    @FXML
    private void initialize() {
        // Keeps the table empty until the user uploads a CSV file.
        csvTable.setPlaceholder(new Label("Upload a CSV file to view its data."));

        // Shows the first action the user needs to take.
        statusLabel.setText("No CSV file selected.");

        updateApiStatus();
    }

    // Opens a file picker so the user can upload a CSV file into the table.
    @FXML
    private void onUploadButtonClick() {
        // Builds the native file chooser dialog.
        FileChooser fileChooser = new FileChooser();

        // Sets the dialog title shown to the user.
        fileChooser.setTitle("Upload CSV File/s");

        // Limits the visible choices to CSV files while still allowing all files if needed.
        fileChooser.getExtensionFilters().addAll(
                new FileChooser.ExtensionFilter("CSV files", "*.csv"),
                new FileChooser.ExtensionFilter("All files", "*.*")
        );

        // Opens the dialog using the current app window as the owner.
        File selectedFile = fileChooser.showOpenDialog(uploadButton.getScene().getWindow());

        // Stops if the user closes the dialog without choosing a file.
        if (selectedFile == null) {
            statusLabel.setText("No CSV file selected.");
            return;
        }

        // Loads the chosen CSV file into the table.
        loadCsvData(selectedFile);
    }

    @FXML
    private void onApiStatusButtonClick() {
        updateApiStatus();
    }

    private void updateApiStatus() {
        try {
            boolean healthy = fastApiClient.isHealthy();
            apiStatusLabel.setText(healthy ? "FastAPI: running" : "FastAPI: unavailable");
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            apiStatusLabel.setText("FastAPI: unavailable");
        }
    }

    // Reads the selected CSV file, builds table columns from the header row, and fills the table.
    private void loadCsvData(File csvFile) {
        // Reads the selected file as UTF-8 text.
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(csvFile), StandardCharsets.UTF_8))) {
            // Reads the first non-empty line as the table header.
            String headerLine = readNextDataLine(reader);
            if (headerLine == null) {
                clearTable();
                statusLabel.setText("Selected CSV file is empty.");
                return;
            }

            // Converts the header line into visible table columns.
            List<String> headers = parseCsvLine(headerLine);
            configureTableColumns(headers);

            // Stores every CSV data row in a JavaFX observable list for the TableView.
            ObservableList<ObservableList<String>> rows = FXCollections.observableArrayList();
            String dataLine;
            while ((dataLine = readNextDataLine(reader)) != null) {
                rows.add(FXCollections.observableArrayList(parseCsvLine(dataLine)));
            }

            // Sends all parsed rows to the table in one update.
            csvTable.setItems(rows);

            // Shows which file was loaded and how many rows it contains.
            statusLabel.setText("Showing " + rows.size() + " rows from " + csvFile.getName());
        } catch (IOException exception) {
            // Clears stale data if the selected file cannot be read.
            clearTable();

            // Displays read errors without crashing the app window.
            statusLabel.setText("Unable to read CSV data: " + exception.getMessage());
        }
    }

    // Creates one TableView column for each CSV header.
    private void configureTableColumns(List<String> headers) {
        // Clears any old columns before adding columns from the current CSV.
        csvTable.getColumns().clear();

        // Builds each column with a cell value factory that reads from the row index.
        for (int columnIndex = 0; columnIndex < headers.size(); columnIndex++) {
            final int currentColumnIndex = columnIndex;
            TableColumn<ObservableList<String>, String> column = new TableColumn<>(headers.get(columnIndex));

            // Pulls the matching value from each row and returns a blank cell when data is missing.
            column.setCellValueFactory(cellData -> {
                ObservableList<String> row = cellData.getValue();
                String cellValue = currentColumnIndex < row.size() ? row.get(currentColumnIndex) : "";
                return new ReadOnlyStringWrapper(cellValue);
            });

            // Gives every column a practical default width for scanning the data.
            column.setPrefWidth(140);

            // Adds the generated column to the visible table.
            csvTable.getColumns().add(column);
        }
    }

    // Removes all table data and columns when a file cannot be loaded.
    private void clearTable() {
        // Clears the visible CSV rows.
        csvTable.getItems().clear();

        // Clears the visible CSV columns.
        csvTable.getColumns().clear();
    }

    // Returns the next non-empty CSV line so blank spacer lines do not create empty table rows.
    private String readNextDataLine(BufferedReader reader) throws IOException {
        String line;
        while ((line = reader.readLine()) != null) {
            // Skips blank lines in the CSV file.
            if (!line.trim().isEmpty()) {
                return line;
            }
        }

        // Signals that the file has no more usable lines.
        return null;
    }

    // Parses a CSV line and supports quoted values that contain commas.
    private List<String> parseCsvLine(String line) {
        // Collects parsed values in their original order.
        List<String> values = new ArrayList<>();

        // Builds the current field one character at a time.
        StringBuilder currentValue = new StringBuilder();

        // Tracks whether the parser is currently inside a quoted CSV field.
        boolean insideQuotes = false;

        // Walks through every character to split only on commas outside quotes.
        for (int index = 0; index < line.length(); index++) {
            char currentCharacter = line.charAt(index);

            // Handles quote characters, including escaped double quotes inside quoted values.
            if (currentCharacter == '"') {
                boolean escapedQuote = insideQuotes
                        && index + 1 < line.length()
                        && line.charAt(index + 1) == '"';
                if (escapedQuote) {
                    currentValue.append('"');
                    index++;
                } else {
                    insideQuotes = !insideQuotes;
                }
            } else if (currentCharacter == ',' && !insideQuotes) {
                // Finishes the current value when a comma appears outside quotes.
                values.add(currentValue.toString().trim());
                currentValue.setLength(0);
            } else {
                // Keeps regular characters as part of the current value.
                currentValue.append(currentCharacter);
            }
        }

        // Adds the final value after the loop reaches the end of the line.
        values.add(currentValue.toString().trim());

        // Returns all parsed values to the table loader.
        return values;
    }
}
