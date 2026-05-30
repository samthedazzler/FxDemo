package com.sam.fxdemo;

import com.sam.fxdemo.api.FastApiClient;
import com.sam.fxdemo.dashboard.AgentLiveSnapshot;
import com.sam.fxdemo.dashboard.AgentReportSnapshot;
import com.sam.fxdemo.dashboard.DashboardInsights;
import com.sam.fxdemo.data.AgentActivityRecord;
import com.sam.fxdemo.data.AgentDatasetLoader;
import com.sam.fxdemo.module1.WorkingHoursAnalyzer;
import com.sam.fxdemo.module1.WorkingHoursSnapshot;
import com.sam.fxdemo.module2.LeaveCoverageAnalyzer;
import com.sam.fxdemo.module2.LeaveCoverageSnapshot;
import com.sam.fxdemo.module3.ShrinkageAnalyzer;
import com.sam.fxdemo.module3.ShrinkageSnapshot;
import eu.hansolo.medusa.Gauge;
import eu.hansolo.medusa.GaugeBuilder;
import io.fair_acc.chartfx.XYChart;
import io.fair_acc.chartfx.axes.spi.DefaultNumericAxis;
import io.fair_acc.chartfx.renderer.spi.BasicDataSetRenderer;
import io.fair_acc.dataset.spi.DoubleDataSet;
import javafx.beans.property.ReadOnlyStringWrapper;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.collections.transformation.FilteredList;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListView;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.stage.FileChooser;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.DecimalFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Function;
import java.util.stream.Collectors;

// Controls the AI workforce dashboard, including overview panels and downloadable reports.
public class HelloController {
    private static final String ALL_DATES = "All dates";
    private static final String ALL_TEAMS = "All teams";
    private static final String ALL_AGENTS = "All agents";
    private static final double CONTRACTED_HOURS_PROXY = 8.0;
    private static final double SLA_TARGET_PERCENT = 95.0;
    private static final Path DATA_DIRECTORY = Path.of("Data");
    private static final URI CSV_WATCH_URI = URI.create("ws://127.0.0.1:8000/ws/csv-watch");

    private final FastApiClient fastApiClient = new FastApiClient();
    private final HttpClient websocketHttpClient = HttpClient.newHttpClient();
    private final ExecutorService dataExecutor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "csv-data-loader");
        thread.setDaemon(true);
        return thread;
    });
    private final AgentDatasetLoader datasetLoader = new AgentDatasetLoader();
    private final WorkingHoursAnalyzer workingHoursAnalyzer = new WorkingHoursAnalyzer();
    private final LeaveCoverageAnalyzer leaveCoverageAnalyzer = new LeaveCoverageAnalyzer();
    private final ShrinkageAnalyzer shrinkageAnalyzer = new ShrinkageAnalyzer();
    private final DashboardInsights dashboardInsights = new DashboardInsights();
    private final DecimalFormat hoursFormat = new DecimalFormat("0.00");
    private final DecimalFormat percentFormat = new DecimalFormat("0.0");

    private List<AgentActivityRecord> allRecords = List.of();

    private final ObservableList<WorkingHoursSnapshot> workingHoursItems = FXCollections.observableArrayList();
    private final FilteredList<WorkingHoursSnapshot> filteredWorkingHours = new FilteredList<>(workingHoursItems);
    private final ObservableList<LeaveCoverageSnapshot> leaveCoverageItems = FXCollections.observableArrayList();
    private final FilteredList<LeaveCoverageSnapshot> filteredLeaveCoverage = new FilteredList<>(leaveCoverageItems);
    private final ObservableList<ShrinkageSnapshot> shrinkageItems = FXCollections.observableArrayList();
    private final FilteredList<ShrinkageSnapshot> filteredShrinkage = new FilteredList<>(shrinkageItems);
    private final ObservableList<AgentLiveSnapshot> liveMonitoringItems = FXCollections.observableArrayList();
    private final FilteredList<AgentLiveSnapshot> filteredLiveMonitoring = new FilteredList<>(liveMonitoringItems);
    private final ObservableList<AgentReportSnapshot> agentReportItems = FXCollections.observableArrayList();
    private final FilteredList<AgentReportSnapshot> filteredAgentReports = new FilteredList<>(agentReportItems);
    private final ObservableList<String> recommendationItems = FXCollections.observableArrayList();

    @FXML private Button uploadButton;
    @FXML private Label statusLabel;
    @FXML private Label apiStatusLabel;
    @FXML private ComboBox<String> dateFilterCombo;
    @FXML private ComboBox<String> teamFilterCombo;
    @FXML private ComboBox<String> agentFilterCombo;

    @FXML private Button dashboardNavButton;
    @FXML private Button analyticsNavButton;
    @FXML private Button leaveNavButton;
    @FXML private Button shrinkageNavButton;

    @FXML private ScrollPane dashboardScrollPane;
    @FXML private VBox dashboardPage;
    @FXML private VBox analyticsPage;
    @FXML private VBox leavePage;
    @FXML private VBox shrinkagePage;

    @FXML private StackPane serviceGaugePane;
    @FXML private StackPane ahtGaugePane;
    @FXML private StackPane occupancyGaugePane;
    @FXML private StackPane shrinkageGaugePane;
    @FXML private Label coverageValueLabel;
    @FXML private Label shrinkageValueLabel;
    @FXML private Label occupancyValueLabel;
    @FXML private Label agentsValueLabel;
    @FXML private Label slaRiskValueLabel;
    @FXML private StackPane serviceLevelChartPane;

    @FXML private TableView<LeaveCoverageSnapshot> coverageTrendTable;
    @FXML private TableView<ShrinkageSnapshot> shrinkageAnalysisTable;
    @FXML private TableView<AgentLiveSnapshot> liveMonitoringTable;
    @FXML private ListView<String> recommendationsList;

    @FXML private Label agentReportNoteLabel;
    @FXML private TableView<AgentReportSnapshot> agentReportTable;
    @FXML private TableView<WorkingHoursSnapshot> workingHoursTable;

    @FXML private Label leaveNoteLabel;
    @FXML private TableView<LeaveCoverageSnapshot> leaveCoverageTable;

    @FXML private Label shrinkageNoteLabel;
    @FXML private TableView<ShrinkageSnapshot> shrinkageTable;

    private Gauge serviceLevelGauge;
    private Gauge ahtGauge;
    private Gauge occupancyGauge;
    private Gauge shrinkageGauge;
    private XYChart serviceLevelChart;
    private WebSocket csvWatchWebSocket;

    @FXML
    private void initialize() {
        configureFilters();
        configureTables();
        configureKpiGauges();
        configureDashboardChart();
        configurePages();
        resetDashboard();
        showDashboardPage();
        updateApiStatus();
        loadDataDirectory("Dashboard ready from Data directory.");
        connectCsvWatchSocket();
    }

    @FXML
    private void onUploadButtonClick() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Upload Agent Breakdown CSV");
        fileChooser.getExtensionFilters().addAll(
                new FileChooser.ExtensionFilter("CSV files", "*.csv"),
                new FileChooser.ExtensionFilter("All files", "*.*")
        );

        File selectedFile = fileChooser.showOpenDialog(uploadButton.getScene().getWindow());
        if (selectedFile == null) {
            statusLabel.setText("No CSV file selected.");
            return;
        }

        loadUploadedCsv(selectedFile);
    }

    @FXML
    private void onApiStatusButtonClick() {
        updateApiStatus();
    }

    @FXML
    private void onDashboardNavClick() {
        showDashboardPage();
    }

    @FXML
    private void onAnalyticsNavClick() {
        showAnalyticsPage();
    }

    @FXML
    private void onLeaveNavClick() {
        showLeavePage();
    }

    @FXML
    private void onShrinkageNavClick() {
        showShrinkagePage();
    }

    @FXML
    private void onExportCoverageTrendClick() {
        exportCsv("coverage_trends.csv", filteredLeaveCoverage, snapshot -> List.of(
                snapshot.activityDate().toString(),
                snapshot.teamName(),
                Integer.toString(snapshot.activeAgents()),
                Integer.toString(snapshot.requiredAgents()),
                percentFormat.format(snapshot.projectedCoveragePercent()) + "%"
        ), List.of("Date", "Team", "Active Agents", "Required Agents", "Projected Coverage"));
    }

    @FXML
    private void onExportShrinkageAnalysisClick() {
        exportCsv("shrinkage_analysis.csv", filteredShrinkage, snapshot -> List.of(
                snapshot.activityDate().toString(),
                snapshot.agentId(),
                snapshot.teamName(),
                percentFormat.format(snapshot.shrinkagePercent()) + "%",
                percentFormat.format(snapshot.occupancyPercent()) + "%",
                snapshot.alert()
        ), List.of("Date", "Agent", "Team", "Shrinkage", "Occupancy", "Alert"));
    }

    @FXML
    private void onExportLiveMonitoringClick() {
        exportCsv("live_monitoring.csv", filteredLiveMonitoring, snapshot -> List.of(
                snapshot.agentId(),
                snapshot.teamName(),
                percentFormat.format(snapshot.occupancyPercent()) + "%",
                snapshot.currentStatus(),
                snapshot.availabilityLabel()
        ), List.of("Agent", "Team", "Occupancy", "Current Status", "Availability"));
    }

    @FXML
    private void onExportRecommendationsClick() {
        exportTextList("ai_recommendations.csv", recommendationItems, "Recommendation");
    }

    @FXML
    private void onExportAgentReportClick() {
        exportCsv("agent_reports.csv", filteredAgentReports, snapshot -> List.of(
                snapshot.agentId(),
                snapshot.teamName(),
                hoursFormat.format(snapshot.trackedHours()),
                hoursFormat.format(snapshot.productiveHours()),
                percentFormat.format(snapshot.shrinkagePercent()) + "%",
                percentFormat.format(snapshot.occupancyPercent()) + "%",
                snapshot.latestStatus(),
                snapshot.recommendation()
        ), List.of("Agent", "Team", "Tracked Hours", "Productive Hours", "Shrinkage", "Occupancy", "Latest Status", "Recommendation"));
    }

    @FXML
    private void onExportSelectedAgentClick() {
        String selectedAgent = agentFilterCombo.getValue();
        if (selectedAgent == null || ALL_AGENTS.equals(selectedAgent)) {
            AgentReportSnapshot selectedRow = agentReportTable.getSelectionModel().getSelectedItem();
            if (selectedRow != null) {
                selectedAgent = selectedRow.agentId();
            }
        }

        if (selectedAgent == null || ALL_AGENTS.equals(selectedAgent)) {
            statusLabel.setText("Select an agent from the dropdown or click a row in the table to export.");
            return;
        }

        final String finalAgentId = selectedAgent;
        List<AgentReportSnapshot> selected = filteredAgentReports.stream()
                .filter(snapshot -> snapshot.agentId().equals(finalAgentId))
                .toList();
        exportCsv(finalAgentId + "_report.csv", selected, snapshot -> List.of(
                snapshot.agentId(),
                snapshot.teamName(),
                hoursFormat.format(snapshot.trackedHours()),
                hoursFormat.format(snapshot.productiveHours()),
                percentFormat.format(snapshot.shrinkagePercent()) + "%",
                percentFormat.format(snapshot.occupancyPercent()) + "%",
                snapshot.latestStatus(),
                snapshot.recommendation()
        ), List.of("Agent", "Team", "Tracked Hours", "Productive Hours", "Shrinkage", "Occupancy", "Latest Status", "Recommendation"));
    }

    @FXML
    private void onExportWorkingHoursClick() {
        exportCsv("working_hours.csv", filteredWorkingHours, snapshot -> List.of(
                snapshot.activityDate().toString(),
                snapshot.agentId(),
                snapshot.teamName(),
                hoursFormat.format(snapshot.shiftSpanHours()),
                hoursFormat.format(snapshot.loggedHours()),
                hoursFormat.format(snapshot.productiveHours()),
                percentFormat.format(snapshot.adherencePercent()) + "%",
                snapshot.overtimeRisk() ? "Review" : "OK"
        ), List.of("Date", "Agent", "Team", "Shift Span", "Logged Hours", "Productive Hours", "Adherence", "OT Risk"));
    }

    @FXML
    private void onExportLeaveCoverageClick() {
        onExportCoverageTrendClick();
    }

    @FXML
    private void onExportShrinkageTableClick() {
        onExportShrinkageAnalysisClick();
    }

    private void updateApiStatus() {
        try {
            boolean healthy = fastApiClient.isHealthy();
            apiStatusLabel.setText(healthy ? "Connected" : "Not Connected");
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            apiStatusLabel.setText("Not Connected");
        }
    }

    public void shutdown() {
        if (csvWatchWebSocket != null) {
            csvWatchWebSocket.sendClose(WebSocket.NORMAL_CLOSURE, "Application closing");
        }
        dataExecutor.shutdownNow();
    }

    private void loadUploadedCsv(File csvFile) {
        try {
            updateDashboardFromRecords(datasetLoader.load(csvFile));
            statusLabel.setText("Dashboard ready from " + csvFile.getName());
        } catch (IOException exception) {
            resetDashboard();
            statusLabel.setText("Unable to read CSV data: " + exception.getMessage());
        }
    }

    private void loadDataDirectory(String successMessage) {
        CompletableFuture
                .supplyAsync(() -> {
                    try {
                        Files.createDirectories(DATA_DIRECTORY);
                        return datasetLoader.loadDirectory(DATA_DIRECTORY);
                    } catch (IOException exception) {
                        throw new DataLoadException(exception);
                    }
                }, dataExecutor)
                .thenAccept(records -> Platform.runLater(() -> {
                    updateDashboardFromRecords(records);
                    long csvCount = countCsvFiles();
                    statusLabel.setText(successMessage + " CSV files: " + csvCount + ", records: " + records.size());
                }))
                .exceptionally(throwable -> {
                    Platform.runLater(() -> statusLabel.setText("Unable to read Data CSV files: " + rootMessage(throwable)));
                    return null;
                });
    }

    private void updateDashboardFromRecords(List<AgentActivityRecord> records) {
        allRecords = records;
        if (records.isEmpty()) {
            resetDashboard();
            statusLabel.setText("No CSV records found in Data directory.");
            return;
        }

        List<WorkingHoursSnapshot> working = workingHoursAnalyzer.analyze(allRecords, CONTRACTED_HOURS_PROXY, SLA_TARGET_PERCENT);
        List<LeaveCoverageSnapshot> leave = leaveCoverageAnalyzer.analyze(allRecords, SLA_TARGET_PERCENT);
        List<ShrinkageSnapshot> shrinkage = shrinkageAnalyzer.analyze(allRecords);

        workingHoursItems.setAll(working);
        leaveCoverageItems.setAll(leave);
        shrinkageItems.setAll(shrinkage);
        liveMonitoringItems.setAll(dashboardInsights.buildLiveSnapshots(allRecords, shrinkage));
        agentReportItems.setAll(dashboardInsights.buildAgentReports(working, shrinkage, allRecords));
        recommendationItems.setAll(dashboardInsights.buildRecommendations(working, leave, shrinkage));

        populateFilters(allRecords);
        applyFilters();
        updateTopCards();

        agentReportNoteLabel.setText("Individual agent reports use the selected agent filter and can be exported as CSV.");
        leaveNoteLabel.setText("Coverage approvals follow the documented 95% rule. Blackout dates and leave balances are not present in the CSV.");
        shrinkageNoteLabel.setText("Shrinkage and occupancy are calculated from Data directory CSV files and can be exported.");
    }

    private void connectCsvWatchSocket() {
        websocketHttpClient.newWebSocketBuilder()
                .buildAsync(CSV_WATCH_URI, new CsvWatchListener())
                .thenAccept(webSocket -> {
                    csvWatchWebSocket = webSocket;
                    Platform.runLater(() -> apiStatusLabel.setText("Connected"));
                })
                .exceptionally(throwable -> {
                    Platform.runLater(() -> statusLabel.setText("CSV websocket unavailable: " + rootMessage(throwable)));
                    return null;
                });
    }

    private long countCsvFiles() {
        try (var stream = Files.list(DATA_DIRECTORY)) {
            return stream
                    .filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().toLowerCase().endsWith(".csv"))
                    .count();
        } catch (IOException exception) {
            return 0;
        }
    }

    private String rootMessage(Throwable throwable) {
        Throwable current = throwable;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current.getMessage() == null ? current.getClass().getSimpleName() : current.getMessage();
    }

    private void configureFilters() {
        dateFilterCombo.getItems().add(ALL_DATES);
        teamFilterCombo.getItems().add(ALL_TEAMS);
        agentFilterCombo.getItems().add(ALL_AGENTS);

        dateFilterCombo.setValue(ALL_DATES);
        teamFilterCombo.setValue(ALL_TEAMS);
        agentFilterCombo.setValue(ALL_AGENTS);

        dateFilterCombo.valueProperty().addListener((observable, oldValue, newValue) -> applyFilters());
        teamFilterCombo.valueProperty().addListener((observable, oldValue, newValue) -> applyFilters());
        agentFilterCombo.valueProperty().addListener((observable, oldValue, newValue) -> applyFilters());
    }

    private void populateFilters(List<AgentActivityRecord> records) {
        Set<String> dates = new TreeSet<>();
        Set<String> teams = new TreeSet<>();
        Set<String> agents = new TreeSet<>();
        for (AgentActivityRecord record : records) {
            dates.add(record.activityDate().toString());
            teams.add(record.teamName());
            agents.add(record.agentId());
        }

        dateFilterCombo.getItems().setAll(ALL_DATES);
        dateFilterCombo.getItems().addAll(dates);
        dateFilterCombo.setValue(ALL_DATES);

        teamFilterCombo.getItems().setAll(ALL_TEAMS);
        teamFilterCombo.getItems().addAll(teams);
        teamFilterCombo.setValue(ALL_TEAMS);

        agentFilterCombo.getItems().setAll(ALL_AGENTS);
        agentFilterCombo.getItems().addAll(agents);
        agentFilterCombo.setValue(ALL_AGENTS);
    }

    private void applyFilters() {
        String selectedDate = dateFilterCombo.getValue();
        String selectedTeam = teamFilterCombo.getValue();
        String selectedAgent = agentFilterCombo.getValue();

        filteredWorkingHours.setPredicate(item ->
                matchesFilter(item.activityDate().toString(), selectedDate, ALL_DATES)
                        && matchesFilter(item.teamName(), selectedTeam, ALL_TEAMS)
                        && matchesFilter(item.agentId(), selectedAgent, ALL_AGENTS));
        filteredLeaveCoverage.setPredicate(item ->
                matchesFilter(item.activityDate().toString(), selectedDate, ALL_DATES)
                        && matchesFilter(item.teamName(), selectedTeam, ALL_TEAMS));
        filteredShrinkage.setPredicate(item ->
                matchesFilter(item.activityDate().toString(), selectedDate, ALL_DATES)
                        && matchesFilter(item.teamName(), selectedTeam, ALL_TEAMS)
                        && matchesFilter(item.agentId(), selectedAgent, ALL_AGENTS));
        filteredLiveMonitoring.setPredicate(item ->
                matchesFilter(item.teamName(), selectedTeam, ALL_TEAMS)
                        && matchesFilter(item.agentId(), selectedAgent, ALL_AGENTS));
        filteredAgentReports.setPredicate(item ->
                matchesFilter(item.teamName(), selectedTeam, ALL_TEAMS)
                        && matchesFilter(item.agentId(), selectedAgent, ALL_AGENTS));

        updateTopCards();
    }

    private boolean matchesFilter(String value, String selectedValue, String allValue) {
        return selectedValue == null || allValue.equals(selectedValue) || value.equals(selectedValue);
    }

    private void updateTopCards() {
        if (filteredLeaveCoverage.isEmpty() && filteredWorkingHours.isEmpty()) {
            coverageValueLabel.setText("0.0%");
            shrinkageValueLabel.setText("0.0%");
            occupancyValueLabel.setText("0.0%");
            agentsValueLabel.setText("0");
            slaRiskValueLabel.setText("-");
            updateKpiGauges(0, 0, 0, 0);
            return;
        }

        double shrinkagePercent = filteredShrinkage.stream()
                .mapToDouble(ShrinkageSnapshot::shrinkagePercent)
                .average().orElse(0.0);
        double occupancyPercent = filteredShrinkage.stream()
                .mapToDouble(ShrinkageSnapshot::occupancyPercent)
                .average().orElse(0.0);
        double coveragePercent = filteredLeaveCoverage.stream()
                .mapToDouble(LeaveCoverageSnapshot::projectedCoveragePercent)
                .average().orElse(0.0);

        coverageValueLabel.setText(percentFormat.format(coveragePercent) + "%");
        shrinkageValueLabel.setText(percentFormat.format(shrinkagePercent) + "%");
        occupancyValueLabel.setText(percentFormat.format(occupancyPercent) + "%");
        agentsValueLabel.setText(Long.toString(filteredAgentReports.stream().map(AgentReportSnapshot::agentId).distinct().count()));
        updateKpiGauges(coveragePercent, 318, occupancyPercent, shrinkagePercent);

        boolean hasSlaRisk = filteredLeaveCoverage.stream().anyMatch(snapshot -> !snapshot.oneMoreLeaveAllowed())
                || filteredWorkingHours.stream().anyMatch(WorkingHoursSnapshot::overtimeRisk);
        slaRiskValueLabel.setText(hasSlaRisk ? "High" : "Low");
    }

    private void configureTables() {
        configureCoverageTrendTable();
        configureShrinkageAnalysisTable();
        configureLiveMonitoringTable();
        configureAgentReportTable();
        configureWorkingHoursTable();
        configureLeaveCoverageTable();
        configureShrinkageTable();

        coverageTrendTable.setItems(filteredLeaveCoverage);
        shrinkageAnalysisTable.setItems(filteredShrinkage);
        liveMonitoringTable.setItems(filteredLiveMonitoring);
        agentReportTable.setItems(filteredAgentReports);
        workingHoursTable.setItems(filteredWorkingHours);
        leaveCoverageTable.setItems(filteredLeaveCoverage);
        shrinkageTable.setItems(filteredShrinkage);
        recommendationsList.setItems(recommendationItems);
    }

    private void configureKpiGauges() {
        serviceLevelGauge = createKpiGauge(81.2, 100, "SL", "%", Color.web("#46d95f"));
        ahtGauge = createKpiGauge(318, 500, "AHT", "s", Color.web("#f59e0b"));
        occupancyGauge = createKpiGauge(78.4, 100, "OCC", "%", Color.web("#a855f7"));
        shrinkageGauge = createKpiGauge(24.5, 100, "SH", "%", Color.web("#3b82f6"));

        serviceGaugePane.getChildren().setAll(serviceLevelGauge);
        ahtGaugePane.getChildren().setAll(ahtGauge);
        occupancyGaugePane.getChildren().setAll(occupancyGauge);
        shrinkageGaugePane.getChildren().setAll(shrinkageGauge);
    }

    private Gauge createKpiGauge(double value, double maxValue, String title, String unit, Color color) {
        Gauge gauge = GaugeBuilder.create()
                .skinType(Gauge.SkinType.SIMPLE)
                .minValue(0)
                .maxValue(maxValue)
                .value(value)
                .title(title)
                .unit(unit)
                .decimals(unit.equals("s") ? 0 : 1)
                .animated(false)
                .valueVisible(false)
                .barColor(color)
                .needleColor(color)
                .tickLabelColor(Color.web("#7f8fa3"))
                .tickMarkColor(Color.web("#25384d"))
                .foregroundBaseColor(Color.web("#e8f0fb"))
                .backgroundPaint(Color.TRANSPARENT)
                .borderPaint(Color.TRANSPARENT)
                .build();
        gauge.setPrefSize(58, 58);
        gauge.setMinSize(58, 58);
        gauge.setMaxSize(58, 58);
        return gauge;
    }

    private void updateKpiGauges(double serviceLevel, double aht, double occupancy, double shrinkage) {
        if (serviceLevelGauge == null) {
            return;
        }
        serviceLevelGauge.setValue(serviceLevel);
        ahtGauge.setValue(aht);
        occupancyGauge.setValue(occupancy);
        shrinkageGauge.setValue(shrinkage);
    }

    private void configureDashboardChart() {
        if (serviceLevelChartPane == null) {
            return;
        }

        DefaultNumericAxis xAxis = new DefaultNumericAxis("Month", 0, 5, 1);
        DefaultNumericAxis yAxis = new DefaultNumericAxis("Service Level", 0, 100, 20);
        serviceLevelChart = new XYChart(xAxis, yAxis);
        serviceLevelChart.setAnimated(false);
        serviceLevelChart.setLegendVisible(false);
        serviceLevelChart.setTitle("");
        serviceLevelChart.getToolBar().setVisible(false);
        serviceLevelChart.getToolBar().setManaged(false);
        serviceLevelChart.setStyle("-fx-background-color: transparent;");

        DoubleDataSet serviceLevel = new DoubleDataSet("Service Level");
        serviceLevel.add(new double[]{0, 1, 2, 3, 4, 5}, new double[]{72, 74, 88, 86, 91, 95});

        DoubleDataSet target = new DoubleDataSet("Target 80%");
        target.add(new double[]{0, 1, 2, 3, 4, 5}, new double[]{80, 80, 80, 80, 80, 80});

        BasicDataSetRenderer renderer = new BasicDataSetRenderer();
        renderer.setDrawMarker(true);
        serviceLevelChart.getRenderers().setAll(renderer);
        serviceLevelChart.getDatasets().setAll(serviceLevel, target);
        serviceLevelChartPane.getChildren().setAll(serviceLevelChart);
    }

    private void configureCoverageTrendTable() {
        coverageTrendTable.getColumns().setAll(
                createColumn("Team", LeaveCoverageSnapshot::teamName, 250),
                createColumn("Coverage", snapshot -> percentFormat.format(snapshot.projectedCoveragePercent()) + "%", 110),
                createColumn("Slots Left", snapshot -> Integer.toString(snapshot.remainingLeaveSlots()), 95),
                createColumn("Recommendation", LeaveCoverageSnapshot::recommendation, 220)
        );
    }

    private void configureShrinkageAnalysisTable() {
        shrinkageAnalysisTable.getColumns().setAll(
                createColumn("Agent", ShrinkageSnapshot::agentId, 120),
                createColumn("Team", ShrinkageSnapshot::teamName, 220),
                createColumn("Shrinkage", snapshot -> percentFormat.format(snapshot.shrinkagePercent()) + "%", 95),
                createColumn("Occupancy", snapshot -> percentFormat.format(snapshot.occupancyPercent()) + "%", 95),
                createColumn("Alert", ShrinkageSnapshot::alert, 150)
        );
    }

    private void configureLiveMonitoringTable() {
        liveMonitoringTable.getColumns().setAll(
                createColumn("Agent", AgentLiveSnapshot::agentId, 120),
                createColumn("OCC", snapshot -> percentFormat.format(snapshot.occupancyPercent()) + "% OCC", 110),
                createColumn("Status", AgentLiveSnapshot::availabilityLabel, 110),
                createColumn("Current State", AgentLiveSnapshot::currentStatus, 130),
                createColumn("Team", AgentLiveSnapshot::teamName, 220)
        );
    }

    private void configureAgentReportTable() {
        agentReportTable.getColumns().setAll(
                createColumn("Agent", AgentReportSnapshot::agentId, 120),
                createColumn("Team", AgentReportSnapshot::teamName, 220),
                createColumn("Tracked", snapshot -> hoursFormat.format(snapshot.trackedHours()) + " h", 95),
                createColumn("Productive", snapshot -> hoursFormat.format(snapshot.productiveHours()) + " h", 100),
                createColumn("Shrinkage", snapshot -> percentFormat.format(snapshot.shrinkagePercent()) + "%", 95),
                createColumn("Occupancy", snapshot -> percentFormat.format(snapshot.occupancyPercent()) + "%", 95),
                createColumn("Latest Status", AgentReportSnapshot::latestStatus, 120),
                createColumn("Recommendation", AgentReportSnapshot::recommendation, 200)
        );
    }

    private void configureWorkingHoursTable() {
        workingHoursTable.getColumns().setAll(
                createColumn("Date", snapshot -> snapshot.activityDate().toString(), 100),
                createColumn("Agent", WorkingHoursSnapshot::agentId, 120),
                createColumn("Shift Span", snapshot -> hoursFormat.format(snapshot.shiftSpanHours()) + " h", 95),
                createColumn("Logged", snapshot -> hoursFormat.format(snapshot.loggedHours()) + " h", 95),
                createColumn("Productive", snapshot -> hoursFormat.format(snapshot.productiveHours()) + " h", 100),
                createColumn("Adherence", snapshot -> percentFormat.format(snapshot.adherencePercent()) + "%", 95),
                createColumn("OT Risk", snapshot -> snapshot.overtimeRisk() ? "Review" : "OK", 90)
        );
    }

    private void configureLeaveCoverageTable() {
        leaveCoverageTable.getColumns().setAll(
                createColumn("Date", snapshot -> snapshot.activityDate().toString(), 100),
                createColumn("Team", LeaveCoverageSnapshot::teamName, 260),
                createColumn("Active", snapshot -> Integer.toString(snapshot.activeAgents()), 85),
                createColumn("Required", snapshot -> Integer.toString(snapshot.requiredAgents()), 85),
                createColumn("Slots Left", snapshot -> Integer.toString(snapshot.remainingLeaveSlots()), 95),
                createColumn("Coverage", snapshot -> percentFormat.format(snapshot.projectedCoveragePercent()) + "%", 95),
                createColumn("Recommendation", LeaveCoverageSnapshot::recommendation, 220)
        );
    }

    private void configureShrinkageTable() {
        shrinkageTable.getColumns().setAll(
                createColumn("Date", snapshot -> snapshot.activityDate().toString(), 100),
                createColumn("Agent", ShrinkageSnapshot::agentId, 120),
                createColumn("Tracked", snapshot -> hoursFormat.format(snapshot.trackedHours()) + " h", 95),
                createColumn("Break", snapshot -> hoursFormat.format(snapshot.breakHours()) + " h", 85),
                createColumn("Lunch", snapshot -> hoursFormat.format(snapshot.lunchHours()) + " h", 85),
                createColumn("Shrinkage", snapshot -> percentFormat.format(snapshot.shrinkagePercent()) + "%", 95),
                createColumn("Occupancy", snapshot -> percentFormat.format(snapshot.occupancyPercent()) + "%", 95),
                createColumn("Alert", ShrinkageSnapshot::alert, 140)
        );
    }

    private <T> TableColumn<T, String> createColumn(String title, Function<T, String> mapper, double width) {
        TableColumn<T, String> column = new TableColumn<>(title);
        column.setCellValueFactory(cellData -> new ReadOnlyStringWrapper(mapper.apply(cellData.getValue())));
        column.setPrefWidth(width);
        return column;
    }

    private void configurePages() {
        setPageVisible(dashboardPage, true);
        setScrollVisible(dashboardScrollPane, true);
        setPageVisible(analyticsPage, false);
        setPageVisible(leavePage, false);
        setPageVisible(shrinkagePage, false);
        updateNavState(dashboardNavButton);
    }

    private void showDashboardPage() {
        setPageVisible(dashboardPage, true);
        setScrollVisible(dashboardScrollPane, true);
        setPageVisible(analyticsPage, false);
        setPageVisible(leavePage, false);
        setPageVisible(shrinkagePage, false);
        updateNavState(dashboardNavButton);
    }

    private void showAnalyticsPage() {
        setPageVisible(dashboardPage, false);
        setScrollVisible(dashboardScrollPane, false);
        setPageVisible(analyticsPage, true);
        setPageVisible(leavePage, false);
        setPageVisible(shrinkagePage, false);
        updateNavState(analyticsNavButton);
    }

    private void showLeavePage() {
        setPageVisible(dashboardPage, false);
        setScrollVisible(dashboardScrollPane, false);
        setPageVisible(analyticsPage, false);
        setPageVisible(leavePage, true);
        setPageVisible(shrinkagePage, false);
        updateNavState(leaveNavButton);
    }

    private void showShrinkagePage() {
        setPageVisible(dashboardPage, false);
        setScrollVisible(dashboardScrollPane, false);
        setPageVisible(analyticsPage, false);
        setPageVisible(leavePage, false);
        setPageVisible(shrinkagePage, true);
        updateNavState(shrinkageNavButton);
    }

    private void setPageVisible(VBox page, boolean visible) {
        page.setVisible(visible);
        page.setManaged(visible);
    }

    private void setScrollVisible(ScrollPane scrollPane, boolean visible) {
        scrollPane.setVisible(visible);
        scrollPane.setManaged(visible);
    }

    private void updateNavState(Button activeButton) {
        List<Button> buttons = List.of(dashboardNavButton, analyticsNavButton, leaveNavButton, shrinkageNavButton);
        for (Button button : buttons) {
            button.getStyleClass().remove("nav-button-active");
        }
        activeButton.getStyleClass().add("nav-button-active");
    }

    private <T> void exportCsv(String defaultName, List<T> rows, Function<T, List<String>> mapper, List<String> headers) {
        if (rows.isEmpty()) {
            statusLabel.setText("No report data available to export.");
            return;
        }

        FileChooser chooser = new FileChooser();
        chooser.setTitle("Save report");
        chooser.setInitialFileName(defaultName);
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("CSV files", "*.csv"));
        File file = chooser.showSaveDialog(uploadButton.getScene().getWindow());
        if (file == null) {
            return;
        }

        StringBuilder builder = new StringBuilder();
        builder.append(String.join(",", headers)).append(System.lineSeparator());
        for (T row : rows) {
            builder.append(mapper.apply(row).stream()
                    .map(this::escapeCsv)
                    .collect(Collectors.joining(",")));
            builder.append(System.lineSeparator());
        }

        try {
            Files.writeString(file.toPath(), builder.toString(), StandardCharsets.UTF_8);
            statusLabel.setText("Exported " + file.getName());
        } catch (IOException exception) {
            statusLabel.setText("Unable to export report: " + exception.getMessage());
        }
    }

    private void exportTextList(String defaultName, List<String> rows, String header) {
        exportCsv(defaultName, rows, row -> List.of(row), List.of(header));
    }

    private String escapeCsv(String value) {
        String safe = value == null ? "" : value;
        if (safe.contains(",") || safe.contains("\"") || safe.contains("\n")) {
            return "\"" + safe.replace("\"", "\"\"") + "\"";
        }
        return safe;
    }

    private void resetDashboard() {
        allRecords = List.of();
        workingHoursItems.clear();
        leaveCoverageItems.clear();
        shrinkageItems.clear();
        liveMonitoringItems.clear();
        agentReportItems.clear();
        recommendationItems.clear();
        recommendationItems.setAll(
                "Rebalance 32 agents from low volume queues. Impact: Improve SL by 2.1pp",
                "Add 20 agents to Email queue in W26. Impact: Reduce wait time by 18%",
                "Review overtime in Tech Support team. Impact: Reduce overtime cost by 8%"
        );
        coverageValueLabel.setText("81.2%");
        shrinkageValueLabel.setText("24.5%");
        occupancyValueLabel.setText("78.4%");
        agentsValueLabel.setText("1,248");
        slaRiskValueLabel.setText("48");
        updateKpiGauges(81.2, 318, 78.4, 24.5);
        agentReportNoteLabel.setText("Select an agent to export an individual report.");
        leaveNoteLabel.setText("Coverage reports will appear here after upload.");
        shrinkageNoteLabel.setText("Shrinkage reports will appear here after upload.");
    }

    private final class CsvWatchListener implements WebSocket.Listener {
        private final StringBuilder messageBuffer = new StringBuilder();

        @Override
        public void onOpen(WebSocket webSocket) {
            WebSocket.Listener.super.onOpen(webSocket);
            Platform.runLater(() -> statusLabel.setText("CSV websocket connected. Watching Data directory."));
        }

        @Override
        public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
            messageBuffer.append(data);
            if (last) {
                String message = messageBuffer.toString();
                messageBuffer.setLength(0);
                if (message.contains("\"csv_changed\"") || message.contains("\"initial\"")) {
                    loadDataDirectory(message.contains("\"initial\"")
                            ? "Initial Data directory load complete."
                            : "Live Data directory refresh complete.");
                }
            }
            webSocket.request(1);
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
            Platform.runLater(() -> statusLabel.setText("CSV websocket closed: " + reason));
            return WebSocket.Listener.super.onClose(webSocket, statusCode, reason);
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            Platform.runLater(() -> statusLabel.setText("CSV websocket error: " + rootMessage(error)));
        }
    }

    private static final class DataLoadException extends RuntimeException {
        private DataLoadException(Throwable cause) {
            super(cause);
        }
    }
}
