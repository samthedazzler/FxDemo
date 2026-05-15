package com.sam.fxdemo.module3;

import java.time.LocalDate;

public record ShrinkageSnapshot(
        LocalDate activityDate,
        String agentId,
        String teamName,
        String organization,
        double trackedHours,
        double occHours,
        double cftHours,
        double breakHours,
        double lunchHours,
        double utiHours,
        double shrinkagePercent,
        double occupancyPercent,
        String alert
) {
}
