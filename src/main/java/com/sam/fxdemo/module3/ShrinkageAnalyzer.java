package com.sam.fxdemo.module3;

import com.sam.fxdemo.data.AgentActivityRecord;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

// Calculates Module 3 metrics from the documented OCC, CFT, break, lunch, and shrinkage formulas.
public class ShrinkageAnalyzer {
    public List<ShrinkageSnapshot> analyze(List<AgentActivityRecord> records) {
        Map<GroupKey, Aggregate> groupedRows = new HashMap<>();

        for (AgentActivityRecord record : records) {
            GroupKey key = new GroupKey(record.activityDate(), record.agentId(), record.teamName(), record.organization());
            Aggregate aggregate = groupedRows.computeIfAbsent(key, ignored -> new Aggregate());
            aggregate.trackedMinutes += record.minutes();

            if ("OCC".equalsIgnoreCase(record.statusGroup())) {
                aggregate.occMinutes += record.minutes();
            } else if ("CFT".equalsIgnoreCase(record.statusGroup())) {
                aggregate.cftMinutes += record.minutes();
            } else if ("UTI".equalsIgnoreCase(record.statusGroup())) {
                aggregate.utiMinutes += record.minutes();
            }

            if ("break".equals(record.status())) {
                aggregate.breakMinutes += record.minutes();
            } else if ("lunch".equals(record.status())) {
                aggregate.lunchMinutes += record.minutes();
            }
        }

        List<ShrinkageSnapshot> snapshots = new ArrayList<>();
        for (Map.Entry<GroupKey, Aggregate> entry : groupedRows.entrySet()) {
            GroupKey key = entry.getKey();
            Aggregate aggregate = entry.getValue();

            double trackedHours = aggregate.trackedMinutes / 60.0;
            double occHours = aggregate.occMinutes / 60.0;
            double cftHours = aggregate.cftMinutes / 60.0;
            double breakHours = aggregate.breakMinutes / 60.0;
            double lunchHours = aggregate.lunchMinutes / 60.0;
            double utiHours = aggregate.utiMinutes / 60.0;
            double shrinkagePercent = aggregate.trackedMinutes == 0.0
                    ? 0.0
                    : ((aggregate.breakMinutes + aggregate.lunchMinutes) / aggregate.trackedMinutes) * 100.0;
            double occupancyPercent = (aggregate.occMinutes + aggregate.cftMinutes) == 0.0
                    ? 0.0
                    : (aggregate.occMinutes / (aggregate.occMinutes + aggregate.cftMinutes)) * 100.0;

            snapshots.add(new ShrinkageSnapshot(
                    key.activityDate(),
                    key.agentId(),
                    key.teamName(),
                    key.organization(),
                    trackedHours,
                    occHours,
                    cftHours,
                    breakHours,
                    lunchHours,
                    utiHours,
                    shrinkagePercent,
                    occupancyPercent,
                    buildAlert(shrinkagePercent, occupancyPercent)
            ));
        }

        snapshots.sort(Comparator
                .comparing(ShrinkageSnapshot::activityDate)
                .thenComparing(ShrinkageSnapshot::agentId));
        return snapshots;
    }

    private String buildAlert(double shrinkagePercent, double occupancyPercent) {
        if (shrinkagePercent > 25.0) {
            return "High shrinkage";
        }
        if (occupancyPercent < 50.0) {
            return "Low occupancy";
        }
        if (occupancyPercent > 85.0) {
            return "Burnout risk";
        }
        return "Normal";
    }

    private record GroupKey(java.time.LocalDate activityDate, String agentId, String teamName, String organization) {
    }

    private static final class Aggregate {
        private double trackedMinutes;
        private double occMinutes;
        private double cftMinutes;
        private double breakMinutes;
        private double lunchMinutes;
        private double utiMinutes;
    }
}
