package com.sam.fxdemo.dashboard;

import com.sam.fxdemo.data.AgentActivityRecord;
import com.sam.fxdemo.module1.WorkingHoursSnapshot;
import com.sam.fxdemo.module2.LeaveCoverageSnapshot;
import com.sam.fxdemo.module3.ShrinkageSnapshot;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

// Builds overview cards, live monitoring rows, and agent summaries from the loaded dataset.
public class DashboardInsights {
    public List<AgentLiveSnapshot> buildLiveSnapshots(List<AgentActivityRecord> records, List<ShrinkageSnapshot> shrinkageSnapshots) {
        Map<String, AgentActivityRecord> latestRecordByAgent = new HashMap<>();
        for (AgentActivityRecord record : records) {
            latestRecordByAgent.merge(record.agentId(), record, (left, right) ->
                    right.endTime().isAfter(left.endTime()) ? right : left);
        }

        Map<String, ShrinkageSnapshot> latestShrinkageByAgent = shrinkageSnapshots.stream()
                .collect(Collectors.toMap(
                        ShrinkageSnapshot::agentId,
                        snapshot -> snapshot,
                        (left, right) -> right.activityDate().isAfter(left.activityDate()) ? right : left
                ));

        List<AgentLiveSnapshot> results = new ArrayList<>();
        for (Map.Entry<String, AgentActivityRecord> entry : latestRecordByAgent.entrySet()) {
            String agentId = entry.getKey();
            AgentActivityRecord latest = entry.getValue();
            ShrinkageSnapshot shrinkage = latestShrinkageByAgent.get(agentId);
            double occupancy = shrinkage == null ? 0.0 : shrinkage.occupancyPercent();
            double trackedHours = shrinkage == null ? 0.0 : shrinkage.trackedHours();
            String availability = switch (latest.status()) {
                case "available", "chat", "email", "email_backlog", "after_contact_work" -> "Available";
                case "break", "lunch" -> "Break";
                default -> "Review";
            };

            results.add(new AgentLiveSnapshot(
                    agentId,
                    latest.teamName(),
                    latest.status(),
                    latest.statusGroup(),
                    occupancy,
                    trackedHours,
                    availability
            ));
        }

        results.sort(Comparator.comparing(AgentLiveSnapshot::agentId));
        return results;
    }

    public List<String> buildRecommendations(List<WorkingHoursSnapshot> working, List<LeaveCoverageSnapshot> leave, List<ShrinkageSnapshot> shrinkage) {
        List<String> recommendations = new ArrayList<>();

        working.stream()
                .filter(WorkingHoursSnapshot::overtimeRisk)
                .limit(2)
                .forEach(snapshot -> recommendations.add(
                        "Overtime review for agent " + snapshot.agentId() + " on " + snapshot.activityDate()
                ));

        leave.stream()
                .filter(snapshot -> !snapshot.oneMoreLeaveAllowed())
                .limit(2)
                .forEach(snapshot -> recommendations.add(
                        "Coverage below 95% if leave is approved for " + snapshot.teamName()
                ));

        shrinkage.stream()
                .filter(snapshot -> snapshot.shrinkagePercent() > 25.0)
                .limit(2)
                .forEach(snapshot -> recommendations.add(
                        "High shrinkage detected for agent " + snapshot.agentId()
                ));

        if (recommendations.isEmpty()) {
            recommendations.add("No immediate SLA risks detected in the uploaded dataset.");
        }

        return recommendations;
    }

    public List<AgentReportSnapshot> buildAgentReports(
            List<WorkingHoursSnapshot> working,
            List<ShrinkageSnapshot> shrinkage,
            List<AgentActivityRecord> records
    ) {
        Map<String, WorkingHoursSnapshot> latestWorking = working.stream()
                .collect(Collectors.toMap(
                        WorkingHoursSnapshot::agentId,
                        snapshot -> snapshot,
                        (left, right) -> right.activityDate().isAfter(left.activityDate()) ? right : left
                ));
        Map<String, ShrinkageSnapshot> latestShrinkage = shrinkage.stream()
                .collect(Collectors.toMap(
                        ShrinkageSnapshot::agentId,
                        snapshot -> snapshot,
                        (left, right) -> right.activityDate().isAfter(left.activityDate()) ? right : left
                ));
        Map<String, AgentActivityRecord> latestRecord = new HashMap<>();
        for (AgentActivityRecord record : records) {
            latestRecord.merge(record.agentId(), record, (left, right) ->
                    right.endTime().isAfter(left.endTime()) ? right : left);
        }

        List<AgentReportSnapshot> reports = new ArrayList<>();
        for (Map.Entry<String, WorkingHoursSnapshot> entry : latestWorking.entrySet()) {
            String agentId = entry.getKey();
            WorkingHoursSnapshot work = entry.getValue();
            ShrinkageSnapshot shrink = latestShrinkage.get(agentId);
            AgentActivityRecord latest = latestRecord.get(agentId);

            double shrinkagePercent = shrink == null ? 0.0 : shrink.shrinkagePercent();
            double occupancyPercent = shrink == null ? 0.0 : shrink.occupancyPercent();
            String latestStatus = latest == null ? "-" : latest.status();
            String recommendation = work.overtimeRisk()
                    ? "Review productive hours"
                    : shrinkagePercent > 25.0
                    ? "Reduce break/lunch shrinkage"
                    : occupancyPercent < 50.0
                    ? "Improve live handling time"
                    : "Operating normally";

            reports.add(new AgentReportSnapshot(
                    agentId,
                    work.teamName(),
                    work.loggedHours(),
                    work.productiveHours(),
                    shrinkagePercent,
                    occupancyPercent,
                    latestStatus,
                    recommendation
            ));
        }

        reports.sort(Comparator.comparing(AgentReportSnapshot::agentId));
        return reports;
    }
}
