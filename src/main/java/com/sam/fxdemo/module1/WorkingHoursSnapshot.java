package com.sam.fxdemo.module1;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public record WorkingHoursSnapshot(
        LocalDate activityDate,
        String agentId,
        String teamName,
        String organization,
        LocalDateTime firstActivity,
        LocalDateTime lastActivity,
        double shiftSpanHours,
        double loggedHours,
        double breakHours,
        double lunchHours,
        double productiveHours,
        double adherencePercent,
        double productivityPercent,
        boolean overtimeRisk
) {
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    public String firstActivityDisplay() {
        return DATE_TIME_FORMATTER.format(firstActivity);
    }

    public String lastActivityDisplay() {
        return DATE_TIME_FORMATTER.format(lastActivity);
    }
}
