package com.sam.fxdemo.dashboard;

public record AgentLiveSnapshot(
        String agentId,
        String teamName,
        String currentStatus,
        String statusGroup,
        double occupancyPercent,
        double trackedHours,
        String availabilityLabel
) {
}
