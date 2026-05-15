package com.sam.fxdemo.data;

import java.time.LocalDate;
import java.time.LocalDateTime;

public record AgentActivityRecord(
        String agentId,
        String teamName,
        String organization,
        String status,
        String statusGroup,
        LocalDateTime startTime,
        LocalDateTime endTime,
        double minutes
) {
    public LocalDate activityDate() {
        return startTime.toLocalDate();
    }
}
