package com.sam.fxdemo.module1;

import com.sam.fxdemo.data.AgentActivityRecord;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

// Converts the raw agent breakdown CSV into agent-day working-hours metrics.
public class WorkingHoursAnalyzer {
    public List<WorkingHoursSnapshot> analyze(List<AgentActivityRecord> records, double contractedHoursProxy, double slaTargetPercent) {
        Map<GroupKey, Aggregate> groupedRows = new HashMap<>();

        for (AgentActivityRecord record : records) {
            GroupKey key = new GroupKey(record.activityDate(), record.agentId(), record.teamName(), record.organization());
            Aggregate aggregate = groupedRows.computeIfAbsent(key, ignored -> new Aggregate(record.startTime(), record.endTime()));
            aggregate.includeWindow(record.startTime(), record.endTime(), record.minutes(), record.status());
        }

        List<WorkingHoursSnapshot> snapshots = new ArrayList<>();
        for (Map.Entry<GroupKey, Aggregate> entry : groupedRows.entrySet()) {
            GroupKey key = entry.getKey();
            Aggregate aggregate = entry.getValue();

            double shiftSpanHours = Math.max(Duration.between(aggregate.firstActivity, aggregate.lastActivity).toMinutes() / 60.0, 0.0);
            double loggedHours = aggregate.totalMinutes / 60.0;
            double breakHours = aggregate.breakMinutes / 60.0;
            double lunchHours = aggregate.lunchMinutes / 60.0;
            double productiveHours = Math.max(loggedHours - breakHours - lunchHours, 0.0);
            double adherencePercent = shiftSpanHours == 0.0 ? 0.0 : Math.min((loggedHours / shiftSpanHours) * 100.0, 100.0);
            double productivityPercent = loggedHours == 0.0 ? 0.0 : (productiveHours / loggedHours) * 100.0;
            boolean overtimeRisk = productiveHours < contractedHoursProxy * (slaTargetPercent / 100.0);

            snapshots.add(new WorkingHoursSnapshot(
                    key.activityDate,
                    key.agentId,
                    key.teamName,
                    key.organization,
                    aggregate.firstActivity,
                    aggregate.lastActivity,
                    shiftSpanHours,
                    loggedHours,
                    breakHours,
                    lunchHours,
                    productiveHours,
                    adherencePercent,
                    productivityPercent,
                    overtimeRisk
            ));
        }

        snapshots.sort(Comparator
                .comparing(WorkingHoursSnapshot::activityDate)
                .thenComparing(WorkingHoursSnapshot::agentId));
        return snapshots;
    }

    private record GroupKey(java.time.LocalDate activityDate, String agentId, String teamName, String organization) {
    }

    private static final class Aggregate {
        private LocalDateTime firstActivity;
        private LocalDateTime lastActivity;
        private double totalMinutes;
        private double breakMinutes;
        private double lunchMinutes;

        private Aggregate(LocalDateTime firstActivity, LocalDateTime lastActivity) {
            this.firstActivity = firstActivity;
            this.lastActivity = lastActivity;
        }

        private void includeWindow(LocalDateTime start, LocalDateTime end, double minutes, String status) {
            if (start.isBefore(firstActivity)) {
                firstActivity = start;
            }
            if (end.isAfter(lastActivity)) {
                lastActivity = end;
            }

            totalMinutes += minutes;
            if ("break".equals(status)) {
                breakMinutes += minutes;
            } else if ("lunch".equals(status)) {
                lunchMinutes += minutes;
            }
        }
    }
}
