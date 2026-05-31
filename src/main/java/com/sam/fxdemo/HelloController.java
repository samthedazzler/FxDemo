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
import java.util.Comparator;
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
    @FXML private VBox sidebar;
    @FXML private Label navSectionLabel;
    @FXML private Button collapseButton;

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

    @FXML private Label alertsBadgeLabel;
    @FXML private VBox alertsContainer;
    @FXML private Label criticalAlertsLabel;
    @FXML private Label warningAlertsLabel;
    @FXML private Label infoAlertsLabel;
    @FXML private Label resolvedAlertsLabel;
    @FXML private Label pendingApprovalsBadgeLabel;
    @FXML private Label leaveRequestsLabel;
    @FXML private Label scheduleRequestsLabel;
    @FXML private Label overtimeRequestsLabel;
    @FXML private VBox warningsContainer;
    @FXML private Label warningsBadgeLabel;
    @FXML private VBox insightsContainer;
    @FXML private VBox feedCol1;
    @FXML private VBox feedCol2;
    @FXML private VBox feedCol3;
    @FXML private Label opsForecastLabel;
    @FXML private Label opsVolumeLabel;
    @FXML private Label opsBacklogLabel;
    @FXML private Label opsSlaBreachedLabel;

    // Custom WFM Dashboard Wireframe Labels (Pages 8 and 9)
    @FXML private Label reqCoverIndLabel;
    @FXML private Label schEfficValLabel;
    @FXML private Label schEfficIndLabel;
    @FXML private Label adherenceValLabel;
    @FXML private Label adherenceIndLabel;
    @FXML private Label attritionValLabel;
    @FXML private Label attritionIndLabel;
    @FXML private Label fcaValLabel;
    @FXML private Label fcaIndLabel;
    @FXML private Label occupancyIndLabel;
    @FXML private Label inOffShIndLabel;
    @FXML private Label gmEstValLabel;
    @FXML private Label gmEstIndLabel;
    @FXML private VBox recommendationsContainer;
    @FXML private Label opsLiveFeedLabel;
    @FXML private Label financeLiveFeedLabel;
    @FXML private Label recruitmentLiveFeedLabel;
    @FXML private Label w23CovLabel;
    @FXML private Label w24CovLabel;
    @FXML private Label w25CovLabel;
    @FXML private Label w26CovLabel;
    @FXML private Label w27CovLabel;
    @FXML private Label w28CovLabel;

    private Gauge serviceLevelGauge;
    private Gauge ahtGauge;
    private Gauge occupancyGauge;
    private Gauge shrinkageGauge;
    private XYChart serviceLevelChart;
    private WebSocket csvWatchWebSocket;
    private boolean sidebarCollapsed = false;

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
    private void onCollapseButtonClick() {
        sidebarCollapsed = !sidebarCollapsed;
        if (sidebarCollapsed) {
            sidebar.setPrefWidth(68.0);
            sidebar.setMinWidth(68.0);
            sidebar.setMaxWidth(68.0);
            navSectionLabel.setVisible(false);
            navSectionLabel.setManaged(false);
            dashboardNavButton.setText("WFM");
            collapseButton.setText(">>");
        } else {
            sidebar.setPrefWidth(226.0);
            sidebar.setMinWidth(226.0);
            sidebar.setMaxWidth(226.0);
            navSectionLabel.setVisible(true);
            navSectionLabel.setManaged(true);
            dashboardNavButton.setText("WFM Dashboard");
            collapseButton.setText("Collapse Menu");
        }
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
            if (healthy) {
                loadDynamicDataFromApi();
            } else {
                resetDashboard();
            }
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            apiStatusLabel.setText("Not Connected");
            resetDashboard();
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
        renderRecommendationRows(recommendationItems);

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
            if (coverageValueLabel != null) coverageValueLabel.setText("0.0%");
            if (shrinkageValueLabel != null) shrinkageValueLabel.setText("0.0%");
            if (occupancyValueLabel != null) occupancyValueLabel.setText("0.0%");
            if (agentsValueLabel != null) agentsValueLabel.setText("0");
            if (slaRiskValueLabel != null) slaRiskValueLabel.setText("-");
            if (schEfficValLabel != null) schEfficValLabel.setText("0.0%");
            if (adherenceValLabel != null) adherenceValLabel.setText("0.0%");
            if (attritionValLabel != null) attritionValLabel.setText("0.0% ann");
            if (fcaValLabel != null) fcaValLabel.setText("0.0%");
            if (gmEstValLabel != null) gmEstValLabel.setText("0.0%");
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

        // 1. REQ COVER (Required Coverage)
        if (coverageValueLabel != null) {
            coverageValueLabel.setText(percentFormat.format(coveragePercent) + "%");
        }
        if (reqCoverIndLabel != null) {
            reqCoverIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (coveragePercent >= 95.0) {
                reqCoverIndLabel.getStyleClass().add("positive-text");
                reqCoverIndLabel.setText("▲ Trending");
            } else {
                reqCoverIndLabel.getStyleClass().add("danger-count");
                reqCoverIndLabel.setText("⚠ Below target");
            }
        }

        // 2. SCH EFFIC (Scheduling Efficiency)
        double schEffic = 100.0 - Math.min(25.0, Math.abs(coveragePercent - 100.0) * 1.5);
        if (schEfficValLabel != null) {
            schEfficValLabel.setText(percentFormat.format(schEffic) + "%");
        }
        if (schEfficIndLabel != null) {
            schEfficIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (schEffic >= 90.0) {
                schEfficIndLabel.getStyleClass().add("positive-text");
                schEfficIndLabel.setText("✓ On track");
            } else {
                schEfficIndLabel.getStyleClass().add("warning-count");
                schEfficIndLabel.setText("⚠ Review");
            }
        }

        // 3. ADHERENCE (Adherence)
        double adherence = filteredWorkingHours.stream()
                .mapToDouble(WorkingHoursSnapshot::adherencePercent)
                .average().orElse(0.0);
        if (adherenceValLabel != null) {
            adherenceValLabel.setText(percentFormat.format(adherence) + "%");
        }
        if (adherenceIndLabel != null) {
            adherenceIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (adherence >= 95.0) {
                adherenceIndLabel.getStyleClass().add("positive-text");
                adherenceIndLabel.setText("✓ On track");
            } else {
                adherenceIndLabel.getStyleClass().add("warning-count");
                adherenceIndLabel.setText("⚠ Off track");
            }
        }

        // 4. ATTRITION (Annualised Attrition)
        double attrition = 5.0 + (shrinkagePercent * 0.15) + (100.0 - occupancyPercent) * 0.1;
        if (attritionValLabel != null) {
            attritionValLabel.setText(percentFormat.format(attrition) + "% ann");
        }
        if (attritionIndLabel != null) {
            attritionIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (attrition <= 10.0) {
                attritionIndLabel.getStyleClass().add("positive-text");
                attritionIndLabel.setText("✓ Healthy");
            } else {
                attritionIndLabel.getStyleClass().add("warning-count");
                attritionIndLabel.setText("⚠ Rising");
            }
        }

        // 5. FCA (Forecast Capacity Alignment / Accuracy)
        double fca = 100.0 - Math.min(30.0, Math.abs(occupancyPercent - 80.0) * 1.2);
        if (fcaValLabel != null) {
            fcaValLabel.setText(percentFormat.format(fca) + "%");
        }
        if (fcaIndLabel != null) {
            fcaIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (fca >= 85.0) {
                fcaIndLabel.getStyleClass().add("positive-text");
                fcaIndLabel.setText("✓ Improving");
            } else {
                fcaIndLabel.getStyleClass().add("warning-count");
                fcaIndLabel.setText("⚠ Adjust");
            }
        }

        // 6. OCCUPANCY (Occupancy)
        if (occupancyValueLabel != null) {
            occupancyValueLabel.setText(percentFormat.format(occupancyPercent) + "%");
        }
        if (occupancyIndLabel != null) {
            occupancyIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (occupancyPercent < 85.0 && occupancyPercent >= 70.0) {
                occupancyIndLabel.getStyleClass().add("positive-text");
                occupancyIndLabel.setText("✓ Healthy");
            } else {
                occupancyIndLabel.getStyleClass().add("warning-count");
                occupancyIndLabel.setText("⚠ Burnout risk");
            }
        }

        // 7. IN-OFF SH (In-Office Shrinkage)
        if (shrinkageValueLabel != null) {
            shrinkageValueLabel.setText(percentFormat.format(shrinkagePercent) + "%");
        }
        if (inOffShIndLabel != null) {
            inOffShIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (shrinkagePercent <= 15.0) {
                inOffShIndLabel.getStyleClass().add("positive-text");
                inOffShIndLabel.setText("✓ On track");
            } else {
                inOffShIndLabel.getStyleClass().add("warning-count");
                inOffShIndLabel.setText("⚠ Review");
            }
        }

        // 8. GM EST (Gross Margin Estimate)
        double gmEst = 30.0 + (occupancyPercent - 75.0) * 0.8 - (shrinkagePercent - 15.0) * 0.5;
        if (gmEstValLabel != null) {
            gmEstValLabel.setText(percentFormat.format(gmEst) + "%");
        }
        if (gmEstIndLabel != null) {
            gmEstIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
            if (gmEst >= 35.0) {
                gmEstIndLabel.getStyleClass().add("positive-text");
                gmEstIndLabel.setText("✓ Met");
            } else {
                gmEstIndLabel.getStyleClass().add("warning-count");
                double gap = 35.0 - gmEst;
                gmEstIndLabel.setText("⚠ -" + percentFormat.format(gap) + "pp");
            }
        }

        if (agentsValueLabel != null) {
            agentsValueLabel.setText(Long.toString(filteredAgentReports.stream().map(AgentReportSnapshot::agentId).distinct().count()));
        }
        updateKpiGauges(coveragePercent, 318, occupancyPercent, shrinkagePercent);

        boolean hasSlaRisk = filteredLeaveCoverage.stream().anyMatch(snapshot -> !snapshot.oneMoreLeaveAllowed())
                || filteredWorkingHours.stream().anyMatch(WorkingHoursSnapshot::overtimeRisk);
        if (slaRiskValueLabel != null) {
            slaRiskValueLabel.setText(hasSlaRisk ? "High" : "Low");
        }

        // Update the Line Chart dynamically from the loaded snapshots
        if (serviceLevelChart != null && !filteredLeaveCoverage.isEmpty()) {
            // Group by week or date
            List<LeaveCoverageSnapshot> sortedSnapshots = filteredLeaveCoverage.stream()
                    .sorted(Comparator.comparing(LeaveCoverageSnapshot::activityDate))
                    .toList();
            
            double[] indices = new double[sortedSnapshots.size()];
            double[] values = new double[sortedSnapshots.size()];
            double[] targetValues = new double[sortedSnapshots.size()];
            
            for (int i = 0; i < sortedSnapshots.size(); i++) {
                indices[i] = i;
                values[i] = sortedSnapshots.get(i).projectedCoveragePercent();
                targetValues[i] = 80.0;
            }
            
            DoubleDataSet serviceLevel = new DoubleDataSet("Coverage");
            serviceLevel.add(indices, values);
            DoubleDataSet target = new DoubleDataSet("Target 80%");
            target.add(indices, targetValues);
            
            Platform.runLater(() -> {
                serviceLevelChart.getDatasets().setAll(serviceLevel, target);
            });
            
            // Set dynamic week labels
            Platform.runLater(() -> {
                if (w23CovLabel != null && sortedSnapshots.size() > 0) {
                    w23CovLabel.setText(percentFormat.format(sortedSnapshots.get(0).projectedCoveragePercent()) + "%");
                }
                if (w24CovLabel != null && sortedSnapshots.size() > 1) {
                    w24CovLabel.setText(percentFormat.format(sortedSnapshots.get(1).projectedCoveragePercent()) + "%");
                } else if (w24CovLabel != null) {
                    w24CovLabel.setText("--");
                }
                if (w25CovLabel != null) w25CovLabel.setText("--");
                if (w26CovLabel != null) w26CovLabel.setText("--");
                if (w27CovLabel != null) w27CovLabel.setText("--");
                if (w28CovLabel != null) w28CovLabel.setText("--");
            });
        }

        // Update Cross-Department Live Feed in local CSV mode
        if (opsLiveFeedLabel != null && financeLiveFeedLabel != null && recruitmentLiveFeedLabel != null) {
            double liveAht = 300.0 + shrinkagePercent * 1.2;
            double cost = 10.0 + (100.0 - occupancyPercent) * 0.05;
            double gmGap = gmEst - 35.0;
            long pendingApp = filteredLeaveCoverage.stream().filter(snapshot -> !snapshot.oneMoreLeaveAllowed()).count();
            
            opsLiveFeedLabel.setText("SL today: " + percentFormat.format(coveragePercent) + "% | AHT: " + (int) liveAht + "s vs 320s est");
            financeLiveFeedLabel.setText("Direct Cost/PPH: €" + hoursFormat.format(cost) + " | GM gap: " + percentFormat.format(gmGap) + "pp");
        }
    }

    private void renderRecommendationRows(List<String> items) {
        if (recommendationsContainer == null) return;
        Platform.runLater(() -> {
            recommendationsContainer.getChildren().clear();
            if (items.isEmpty()) {
                Label noRecLabel = new Label("✓ No immediate SLA risks detected.");
                noRecLabel.setStyle("-fx-text-fill: #8b9aab; -fx-font-size: 11px;");
                recommendationsContainer.getChildren().add(noRecLabel);
                return;
            }
            for (String item : items) {
                javafx.scene.layout.VBox row = new javafx.scene.layout.VBox();
                row.setSpacing(6);
                row.setStyle("-fx-padding: 8; -fx-background-color: #0d2030; -fx-background-radius: 5; -fx-border-color: #1a3045; -fx-border-radius: 5;");
                
                javafx.scene.layout.HBox topRow = new javafx.scene.layout.HBox();
                topRow.setSpacing(6);
                topRow.setAlignment(javafx.geometry.Pos.CENTER_LEFT);
                
                Label warningDot = new Label("⚠");
                warningDot.getStyleClass().add("alert-warning");
                warningDot.setStyle("-fx-font-weight: bold; -fx-font-size: 13px;");
                
                Label msgLabel = new Label(item);
                msgLabel.setStyle("-fx-text-fill: #eef5ff; -fx-font-size: 12px; -fx-font-weight: bold;");
                topRow.getChildren().addAll(warningDot, msgLabel);
                
                Label suggestLabel = new Label("→ Recommend reviewing staffing levels and schedules immediately.");
                suggestLabel.setStyle("-fx-text-fill: #a7b4c5; -fx-font-size: 11px; -fx-padding: 0 0 0 16;");
                
                javafx.scene.layout.HBox actionsRow = new javafx.scene.layout.HBox();
                actionsRow.setSpacing(8);
                actionsRow.setStyle("-fx-padding: 4 0 0 16;");
                Button acceptBtn = new Button("Accept");
                acceptBtn.getStyleClass().add("tiny-select");
                Button modifyBtn = new Button("Modify");
                modifyBtn.getStyleClass().add("tiny-select");
                Button dismissBtn = new Button("Dismiss");
                dismissBtn.getStyleClass().add("tiny-select");
                actionsRow.getChildren().addAll(acceptBtn, modifyBtn, dismissBtn);
                
                row.getChildren().addAll(topRow, suggestLabel, actionsRow);
                recommendationsContainer.getChildren().add(row);
            }
        });
    }

    private void configureTables() {
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

        if (serviceGaugePane != null) {
            serviceGaugePane.getChildren().setAll(serviceLevelGauge);
        }
        if (ahtGaugePane != null) {
            ahtGaugePane.getChildren().setAll(ahtGauge);
        }
        if (occupancyGaugePane != null) {
            occupancyGaugePane.getChildren().setAll(occupancyGauge);
        }
        if (shrinkageGaugePane != null) {
            shrinkageGaugePane.getChildren().setAll(shrinkageGauge);
        }
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
        List<Button> buttons = java.util.Arrays.asList(dashboardNavButton, analyticsNavButton, leaveNavButton, shrinkageNavButton);
        for (Button button : buttons) {
            if (button != null) {
                button.getStyleClass().remove("nav-button-active");
            }
        }
        if (activeButton != null) {
            activeButton.getStyleClass().add("nav-button-active");
        }
    }

    private <T> void exportCsv(String defaultName, List<T> rows, Function<T, List<String>> mapper, List<String> headers) {


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

        coverageValueLabel.setText("0.0%");
        shrinkageValueLabel.setText("0.0%");
        occupancyValueLabel.setText("0.0%");
        agentsValueLabel.setText("0");
        slaRiskValueLabel.setText("-");
        updateKpiGauges(0, 0, 0, 0);

        if (alertsBadgeLabel != null) alertsBadgeLabel.setText("0");
        if (alertsContainer != null) alertsContainer.getChildren().clear();
        if (criticalAlertsLabel != null) criticalAlertsLabel.setText("-");
        if (warningAlertsLabel != null) warningAlertsLabel.setText("-");
        if (infoAlertsLabel != null) infoAlertsLabel.setText("-");
        if (resolvedAlertsLabel != null) resolvedAlertsLabel.setText("-");
        if (pendingApprovalsBadgeLabel != null) pendingApprovalsBadgeLabel.setText("-");
        if (leaveRequestsLabel != null) leaveRequestsLabel.setText("-");
        if (scheduleRequestsLabel != null) scheduleRequestsLabel.setText("-");
        if (overtimeRequestsLabel != null) overtimeRequestsLabel.setText("-");
        if (warningsContainer != null) warningsContainer.getChildren().clear();
        if (warningsBadgeLabel != null) warningsBadgeLabel.setText("-");
        if (insightsContainer != null) insightsContainer.getChildren().clear();
        if (feedCol1 != null) feedCol1.getChildren().clear();
        if (feedCol2 != null) feedCol2.getChildren().clear();
        if (feedCol3 != null) feedCol3.getChildren().clear();
        if (reqCoverIndLabel != null) reqCoverIndLabel.setText("-");
        if (schEfficValLabel != null) schEfficValLabel.setText("0.0%");
        if (schEfficIndLabel != null) schEfficIndLabel.setText("-");
        if (adherenceValLabel != null) adherenceValLabel.setText("0.0%");
        if (adherenceIndLabel != null) adherenceIndLabel.setText("-");
        if (attritionValLabel != null) attritionValLabel.setText("0.0% ann");
        if (attritionIndLabel != null) attritionIndLabel.setText("-");
        if (fcaValLabel != null) fcaValLabel.setText("0.0%");
        if (fcaIndLabel != null) fcaIndLabel.setText("-");
        if (inOffShIndLabel != null) inOffShIndLabel.setText("-");
        if (gmEstValLabel != null) gmEstValLabel.setText("0.0%");
        if (gmEstIndLabel != null) gmEstIndLabel.setText("-");
        if (recommendationsContainer != null) recommendationsContainer.getChildren().clear();
        if (opsLiveFeedLabel != null) opsLiveFeedLabel.setText("SL today: 0.0% | AHT: 0s");
        if (financeLiveFeedLabel != null) financeLiveFeedLabel.setText("Direct Cost/PPH: €0.00 | GM gap: 0.0pp");
        if (recruitmentLiveFeedLabel != null) recruitmentLiveFeedLabel.setText("0 pending hire approvals | W26 NHT confirmed");
        if (w23CovLabel != null) w23CovLabel.setText("--");
        if (w24CovLabel != null) w24CovLabel.setText("--");
        if (w25CovLabel != null) w25CovLabel.setText("--");
        if (w26CovLabel != null) w26CovLabel.setText("--");
        if (w27CovLabel != null) w27CovLabel.setText("--");
        if (w28CovLabel != null) w28CovLabel.setText("--");
        if (opsForecastLabel != null) opsForecastLabel.setText("-");
        if (opsVolumeLabel != null) opsVolumeLabel.setText("-");
        if (opsBacklogLabel != null) opsBacklogLabel.setText("-");
        if (opsSlaBreachedLabel != null) opsSlaBreachedLabel.setText("-");

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

    private void loadDynamicDataFromApi() {
        try {
            // Fetch live API payloads
            String kpisJson = fastApiClient.getDashboardKpis();
            String trendJson = fastApiClient.getCoverageTrend();
            String liveFeedJson = fastApiClient.getLiveFeed();
            String adherenceJson = fastApiClient.getRtmAdherence();
            
            // Extract top KPI metrics
            double slRaw = getJsonDoubleValue(kpisJson, "sl_today");
            final double slToday = (slRaw == 0.0) ? 81.2 : slRaw;
            
            double reqCoverage = getJsonDoubleValue(kpisJson, "req_coverage_rate");
            double schedulingEff = getJsonDoubleValue(kpisJson, "scheduling_efficiency");
            double occupancy = getJsonDoubleValue(kpisJson, "occupancy");
            double shrinkage = getJsonDoubleValue(kpisJson, "in_office_shrinkage");
            
            double adherence = getJsonDoubleValue(kpisJson, "adherence_rate");
            double attrition = getJsonDoubleValue(kpisJson, "annualised_attrition");
            double fca = getJsonDoubleValue(kpisJson, "forecast_accuracy");
            double gmEst = getJsonDoubleValue(kpisJson, "gm_estimate");
            
            // Extract cross-department operations SL and AHT
            int ahtRaw = getJsonIntValue(kpisJson, "aht_actual");
            final int ahtActual = (ahtRaw == 0) ? 318 : ahtRaw;
            
            // Set top cards labels
            Platform.runLater(() -> {
                // 1. REQ COVER
                if (coverageValueLabel != null) {
                    coverageValueLabel.setText(percentFormat.format(reqCoverage) + "%");
                }
                if (reqCoverIndLabel != null) {
                    reqCoverIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (reqCoverage >= 95.0) {
                        reqCoverIndLabel.getStyleClass().add("positive-text");
                        reqCoverIndLabel.setText("▲ Trending");
                    } else {
                        reqCoverIndLabel.getStyleClass().add("danger-count");
                        reqCoverIndLabel.setText("⚠ Below target");
                    }
                }

                // 2. SCH EFFIC
                if (schEfficValLabel != null) {
                    schEfficValLabel.setText(percentFormat.format(schedulingEff) + "%");
                }
                if (schEfficIndLabel != null) {
                    schEfficIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (schedulingEff >= 75.0) {
                        schEfficIndLabel.getStyleClass().add("positive-text");
                        schEfficIndLabel.setText("✓ On track");
                    } else {
                        schEfficIndLabel.getStyleClass().add("warning-count");
                        schEfficIndLabel.setText("⚠ Review");
                    }
                }

                // 3. ADHERENCE
                if (adherenceValLabel != null) {
                    adherenceValLabel.setText(percentFormat.format(adherence) + "%");
                }
                if (adherenceIndLabel != null) {
                    adherenceIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (adherence >= 95.0) {
                        adherenceIndLabel.getStyleClass().add("positive-text");
                        adherenceIndLabel.setText("✓ On track");
                    } else {
                        adherenceIndLabel.getStyleClass().add("warning-count");
                        adherenceIndLabel.setText("⚠ Off track");
                    }
                }

                // 4. ATTRITION
                if (attritionValLabel != null) {
                    attritionValLabel.setText(percentFormat.format(attrition) + "% ann");
                }
                if (attritionIndLabel != null) {
                    attritionIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (attrition <= 10.0) {
                        attritionIndLabel.getStyleClass().add("positive-text");
                        attritionIndLabel.setText("✓ Healthy");
                    } else {
                        attritionIndLabel.getStyleClass().add("warning-count");
                        attritionIndLabel.setText("⚠ Rising");
                    }
                }

                // 5. FCA
                if (fcaValLabel != null) {
                    fcaValLabel.setText(percentFormat.format(fca) + "%");
                }
                if (fcaIndLabel != null) {
                    fcaIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (fca >= 85.0) {
                        fcaIndLabel.getStyleClass().add("positive-text");
                        fcaIndLabel.setText("✓ Improving");
                    } else {
                        fcaIndLabel.getStyleClass().add("warning-count");
                        fcaIndLabel.setText("⚠ Adjust");
                    }
                }

                // 6. OCCUPANCY
                if (occupancyValueLabel != null) {
                    occupancyValueLabel.setText(percentFormat.format(occupancy) + "%");
                }
                if (occupancyIndLabel != null) {
                    occupancyIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (occupancy < 85.0 && occupancy >= 70.0) {
                        occupancyIndLabel.getStyleClass().add("positive-text");
                        occupancyIndLabel.setText("✓ Healthy");
                    } else {
                        occupancyIndLabel.getStyleClass().add("warning-count");
                        occupancyIndLabel.setText("⚠ Burnout risk");
                    }
                }

                // 7. IN-OFF SH
                if (shrinkageValueLabel != null) {
                    shrinkageValueLabel.setText(percentFormat.format(shrinkage) + "%");
                }
                if (inOffShIndLabel != null) {
                    inOffShIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (shrinkage <= 12.0) {
                        inOffShIndLabel.getStyleClass().add("positive-text");
                        inOffShIndLabel.setText("✓ On track");
                    } else {
                        inOffShIndLabel.getStyleClass().add("warning-count");
                        inOffShIndLabel.setText("⚠ Review");
                    }
                }

                // 8. GM EST
                if (gmEstValLabel != null) {
                    gmEstValLabel.setText(percentFormat.format(gmEst) + "%");
                }
                if (gmEstIndLabel != null) {
                    gmEstIndLabel.getStyleClass().removeAll("positive-text", "warning-count", "danger-count");
                    if (gmEst >= 35.0) {
                        gmEstIndLabel.getStyleClass().add("positive-text");
                        gmEstIndLabel.setText("✓ Met");
                    } else {
                        gmEstIndLabel.getStyleClass().add("warning-count");
                        double gap = 35.0 - gmEst;
                        gmEstIndLabel.setText("⚠ -" + percentFormat.format(gap) + "pp");
                    }
                }

                if (agentsValueLabel != null) {
                    agentsValueLabel.setText("48");
                }
                updateKpiGauges(slToday, ahtActual, occupancy, shrinkage);
                
                // Populate Operations Snapshot
                opsForecastLabel.setText("12,500");
                opsVolumeLabel.setText("ASA: " + getJsonIntValue(liveFeedJson, "avg_speed_of_answer") + "s");
                opsBacklogLabel.setText(getJsonIntValue(liveFeedJson, "calls_in_queue") + " calls");
                opsSlaBreachedLabel.setText("Abandon: " + getJsonDoubleValue(liveFeedJson, "abandon_rate") + "%");
                
                // Populate Cross-Department Live Feed columns
                double liveSl = getJsonDoubleValue(liveFeedJson, "service_level_current");
                int liveAht = getJsonIntValue(liveFeedJson, "aht_actual");
                double cost = 10.39;
                double gmGap = getJsonDoubleValue(kpisJson, "gm_gap_pp");
                if (gmGap == 0.0) gmGap = -0.2;
                int pendingApp = 4;
                
                if (opsLiveFeedLabel != null) {
                    opsLiveFeedLabel.setText("SL today: " + percentFormat.format(liveSl) + "% | AHT: " + liveAht + "s vs 320s est");
                }
                if (financeLiveFeedLabel != null) {
                    financeLiveFeedLabel.setText("Direct Cost/PPH: €" + hoursFormat.format(cost) + " | GM gap: " + percentFormat.format(gmGap) + "pp");
                }
                if (recruitmentLiveFeedLabel != null) {
                    recruitmentLiveFeedLabel.setText(pendingApp + " pending hire approvals | W26 NHT confirmed");
                }
            });
            
            // Parse recommendations
            parseRecommendations(kpisJson);
            
            // Parse coverage trend for chart & week labels
            updateCoverageTrend(trendJson);
            
            // Parse live monitoring
            parseLiveMonitoring(adherenceJson);
            
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            Platform.runLater(() -> statusLabel.setText("Failed to load live data from API: " + exception.getMessage()));
        }
    }

    private void updateCoverageTrend(String trendJson) {
        if (trendJson == null) return;
        
        // Parse the coverage trend
        List<String> weeks = new java.util.ArrayList<>();
        List<Double> rates = new java.util.ArrayList<>();
        
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\"week\"\\s*:\\s*\"([^\"]*)\"[^}]*\"coverage_rate\"\\s*:\\s*([0-9]+)").matcher(trendJson);
        while (matcher.find()) {
            weeks.add(matcher.group(1));
            rates.add(Double.parseDouble(matcher.group(2)));
        }
        
        if (weeks.isEmpty()) {
            matcher = java.util.regex.Pattern.compile("\"coverage_rate\"\\s*:\\s*([0-9]+)[^}]*\"week\"\\s*:\\s*\"([^\"]*)\"").matcher(trendJson);
            while (matcher.find()) {
                rates.add(Double.parseDouble(matcher.group(1)));
                weeks.add(matcher.group(2));
            }
        }
        
        if (weeks.isEmpty()) return;
        
        // Update Chart
        updateDashboardChartFromData(trendJson);
        
        // Update Labels (W23 to W28)
        Platform.runLater(() -> {
            for (int i = 0; i < weeks.size(); i++) {
                String w = weeks.get(i);
                double rate = rates.get(i);
                String valStr = percentFormat.format(rate) + "%";
                if ("W23".equalsIgnoreCase(w) && w23CovLabel != null) w23CovLabel.setText(valStr);
                else if ("W24".equalsIgnoreCase(w) && w24CovLabel != null) w24CovLabel.setText(valStr);
                else if ("W25".equalsIgnoreCase(w) && w25CovLabel != null) w25CovLabel.setText(valStr);
                else if ("W26".equalsIgnoreCase(w) && w26CovLabel != null) w26CovLabel.setText(valStr);
                else if ("W27".equalsIgnoreCase(w) && w27CovLabel != null) w27CovLabel.setText(valStr);
                else if ("W28".equalsIgnoreCase(w) && w28CovLabel != null) w28CovLabel.setText(valStr);
            }
        });
    }

    private javafx.scene.layout.HBox createAlertRow(String text, String type, String time) {
        javafx.scene.layout.HBox row = new javafx.scene.layout.HBox();
        row.getStyleClass().add("alert-row");
        row.setSpacing(9);
        row.setAlignment(javafx.geometry.Pos.CENTER_LEFT);
        
        Label dot = new Label("●");
        if ("critical".equalsIgnoreCase(type) || "red".equalsIgnoreCase(type) || "danger".equalsIgnoreCase(type)) {
            dot.getStyleClass().add("alert-critical");
        } else if ("warning".equalsIgnoreCase(type) || "amber".equalsIgnoreCase(type)) {
            dot.getStyleClass().add("alert-warning");
        } else {
            dot.getStyleClass().add("alert-info");
        }
        
        Label msg = new Label(text);
        msg.setStyle("-fx-text-fill: #eef5ff; -fx-font-size: 11px;");
        
        javafx.scene.layout.Region spacer = new javafx.scene.layout.Region();
        javafx.scene.layout.HBox.setHgrow(spacer, javafx.scene.layout.Priority.ALWAYS);
        
        Label timeLabel = new Label(time);
        timeLabel.setStyle("-fx-text-fill: #8b9aab; -fx-font-size: 10px;");
        
        row.getChildren().addAll(dot, msg, spacer, timeLabel);
        return row;
    }

    private void updateDashboardChartFromData(String trendJson) {
        if (serviceLevelChart == null || trendJson == null) return;
        
        List<Double> coverageRates = new java.util.ArrayList<>();
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\"coverage_rate\"\\s*:\\s*([0-9]+)").matcher(trendJson);
        while (matcher.find()) {
            coverageRates.add(Double.parseDouble(matcher.group(1)));
        }
        
        if (coverageRates.isEmpty()) return;
        
        double[] indices = new double[coverageRates.size()];
        double[] values = new double[coverageRates.size()];
        double[] targetValues = new double[coverageRates.size()];
        
        for (int i = 0; i < coverageRates.size(); i++) {
            indices[i] = i;
            values[i] = coverageRates.get(i);
            targetValues[i] = 80.0;
        }
        
        DoubleDataSet serviceLevel = new DoubleDataSet("Service Level");
        serviceLevel.add(indices, values);
        
        DoubleDataSet target = new DoubleDataSet("Target 80%");
        target.add(indices, targetValues);
        
        Platform.runLater(() -> {
            serviceLevelChart.getDatasets().setAll(serviceLevel, target);
        });
    }

    private double getJsonDoubleValue(String json, String key) {
        if (json == null) return 0.0;
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\"" + key + "\"\\s*:\\s*(-?[0-9]*\\.?[0-9]+)").matcher(json);
        if (matcher.find()) {
            return Double.parseDouble(matcher.group(1));
        }
        return 0.0;
    }

    private int getJsonIntValue(String json, String key) {
        if (json == null) return 0;
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\"" + key + "\"\\s*:\\s*(-?[0-9]+)").matcher(json);
        if (matcher.find()) {
            return Integer.parseInt(matcher.group(1));
        }
        return 0;
    }

    private String getJsonStringValue(String json, String key) {
        if (json == null) return "";
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"").matcher(json);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "";
    }

    private void parseRecommendations(String json) {
        Platform.runLater(() -> recommendationItems.clear());
        if (json == null) return;
        int index = json.indexOf("\"ai_recommendations\"");
        if (index == -1) return;
        int startBracket = json.indexOf("[", index);
        if (startBracket == -1) return;
        int endBracket = json.indexOf("]", startBracket);
        if (endBracket == -1) return;
        
        String arrayContent = json.substring(startBracket + 1, endBracket);
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\\{(.*?)\\}").matcher(arrayContent);
        java.util.List<String> items = new java.util.ArrayList<>();
        while (matcher.find()) {
            String objectContent = matcher.group(1);
            String rawObj = "{" + objectContent + "}";
            String message = getJsonStringValue(rawObj, "message");
            String action = getJsonStringValue(rawObj, "action");
            if (!message.isEmpty()) {
                if (!action.isEmpty()) {
                    items.add(message + " (" + action + ")");
                } else {
                    items.add(message);
                }
            }
        }
        Platform.runLater(() -> recommendationItems.setAll(items));
    }

    private void parseLiveMonitoring(String json) {
        Platform.runLater(() -> liveMonitoringItems.clear());
        if (json == null) return;
        int index = json.indexOf("\"agents\"");
        if (index == -1) return;
        int startBracket = json.indexOf("[", index);
        if (startBracket == -1) return;
        int endBracket = json.indexOf("]", startBracket);
        if (endBracket == -1) return;
        
        String arrayContent = json.substring(startBracket + 1, endBracket);
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("\\{(.*?)\\}").matcher(arrayContent);
        java.util.List<AgentLiveSnapshot> items = new java.util.ArrayList<>();
        while (matcher.find()) {
            String objectContent = matcher.group(1);
            String rawObj = "{" + objectContent + "}";
            String agentName = getJsonStringValue(rawObj, "agent_name");
            String scheduledStatus = getJsonStringValue(rawObj, "scheduled_status");
            String actualStatus = getJsonStringValue(rawObj, "actual_status");
            String infraction = getJsonStringValue(rawObj, "infraction");
            
            String availabilityLabel = (infraction == null || infraction.isEmpty() || "null".equals(infraction)) ? "Adhering" : infraction;
            
            items.add(new AgentLiveSnapshot(
                agentName,
                "Billing",
                actualStatus,
                scheduledStatus,
                82.4,
                8.0,
                availabilityLabel
            ));
        }
        Platform.runLater(() -> liveMonitoringItems.setAll(items));
    }
}
