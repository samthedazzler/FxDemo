package com.sam.fxdemo.module2;

import java.time.LocalDate;

public record LeaveCoverageSnapshot(
        LocalDate activityDate,
        String teamName,
        String organization,
        int activeAgents,
        int requiredAgents,
        int maxSimultaneousLeave,
        int remainingLeaveSlots,
        double projectedCoveragePercent,
        boolean oneMoreLeaveAllowed,
        String recommendation
) {
}
