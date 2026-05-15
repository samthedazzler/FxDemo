package com.sam.fxdemo.module2;

import com.sam.fxdemo.data.AgentActivityRecord;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

// Builds a leave-capacity view from the documented 95% coverage rule.
public class LeaveCoverageAnalyzer {
    public List<LeaveCoverageSnapshot> analyze(List<AgentActivityRecord> records, double slaTargetPercent) {
        Map<GroupKey, Set<String>> activeAgentsByTeamDay = new HashMap<>();

        for (AgentActivityRecord record : records) {
            GroupKey key = new GroupKey(record.activityDate(), record.teamName(), record.organization());
            activeAgentsByTeamDay.computeIfAbsent(key, ignored -> new HashSet<>()).add(record.agentId());
        }

        List<LeaveCoverageSnapshot> snapshots = new ArrayList<>();
        for (Map.Entry<GroupKey, Set<String>> entry : activeAgentsByTeamDay.entrySet()) {
            GroupKey key = entry.getKey();
            int activeAgents = entry.getValue().size();
            int requiredAgents = (int) Math.ceil(activeAgents * (slaTargetPercent / 100.0));
            int maxSimultaneousLeave = Math.max(activeAgents - requiredAgents, 0);
            int remainingLeaveSlots = maxSimultaneousLeave;
            int postRequestAgents = Math.max(activeAgents - 1, 0);
            double projectedCoveragePercent = activeAgents == 0 ? 0.0 : (postRequestAgents * 100.0) / activeAgents;
            boolean oneMoreLeaveAllowed = postRequestAgents >= requiredAgents;
            String recommendation = oneMoreLeaveAllowed
                    ? "One additional leave can be approved"
                    : "Deny additional leave at current coverage";

            snapshots.add(new LeaveCoverageSnapshot(
                    key.activityDate(),
                    key.teamName(),
                    key.organization(),
                    activeAgents,
                    requiredAgents,
                    maxSimultaneousLeave,
                    remainingLeaveSlots,
                    projectedCoveragePercent,
                    oneMoreLeaveAllowed,
                    recommendation
            ));
        }

        snapshots.sort(Comparator
                .comparing(LeaveCoverageSnapshot::activityDate)
                .thenComparing(LeaveCoverageSnapshot::teamName));
        return snapshots;
    }

    private record GroupKey(java.time.LocalDate activityDate, String teamName, String organization) {
    }
}
