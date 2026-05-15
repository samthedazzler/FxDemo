package com.sam.fxdemo.dashboard;

public record AgentReportSnapshot(
        String agentId,
        String teamName,
        double trackedHours,
        double productiveHours,
        double shrinkagePercent,
        double occupancyPercent,
        String latestStatus,
        String recommendation
) {
}
