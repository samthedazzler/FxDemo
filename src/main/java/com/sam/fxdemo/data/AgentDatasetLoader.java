package com.sam.fxdemo.data;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

// Loads the agent breakdown CSV into normalized activity records shared by all modules.
public class AgentDatasetLoader {
    private static final DateTimeFormatter CSV_DATE_TIME = DateTimeFormatter.ofPattern("M/d/yyyy h:mm:ss a", Locale.US);

    public List<AgentActivityRecord> loadDirectory(Path dataDirectory) throws IOException {
        if (!Files.isDirectory(dataDirectory)) {
            return List.of();
        }

        List<File> csvFiles;
        try (var stream = Files.list(dataDirectory)) {
            csvFiles = stream
                    .filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".csv"))
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .map(Path::toFile)
                    .toList();
        }

        List<AgentActivityRecord> records = new ArrayList<>();
        for (File csvFile : csvFiles) {
            records.addAll(load(csvFile));
        }
        return records;
    }

    public List<AgentActivityRecord> load(File csvFile) throws IOException {
        List<AgentActivityRecord> records = new ArrayList<>();

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(csvFile), StandardCharsets.UTF_8))) {
            String headerLine = readNextDataLine(reader);
            if (headerLine == null) {
                return List.of();
            }

            List<String> headers = parseCsvLine(headerLine);
            Map<String, Integer> headerIndex = buildHeaderIndex(headers);

            String line;
            while ((line = readNextDataLine(reader)) != null) {
                List<String> values = parseCsvLine(line);
                String agentId = getValue(values, headerIndex, "Agent Id");
                if (agentId.isBlank()) {
                    continue;
                }

                LocalDateTime start = parseDateTime(firstNonBlank(
                        getValue(values, headerIndex, "Local Start Time"),
                        getValue(values, headerIndex, "local_interval_sta"),
                        getValue(values, headerIndex, "Interval Start Time ")
                ));
                LocalDateTime end = parseDateTime(firstNonBlank(
                        getValue(values, headerIndex, "Local End Time"),
                        getValue(values, headerIndex, "Local Interval End"),
                        getValue(values, headerIndex, "Utc End Time")
                ));
                if (start == null || end == null) {
                    continue;
                }

                records.add(new AgentActivityRecord(
                        agentId,
                        getValue(values, headerIndex, "SRT Team"),
                        getValue(values, headerIndex, "Organization"),
                        getValue(values, headerIndex, "Status").toLowerCase(Locale.ROOT),
                        getValue(values, headerIndex, "Status Group"),
                        start,
                        end,
                        parseDouble(getValue(values, headerIndex, "time_in_interval_m"))
                ));
            }
        }

        return records;
    }

    private Map<String, Integer> buildHeaderIndex(List<String> headers) {
        Map<String, Integer> index = new HashMap<>();
        for (int position = 0; position < headers.size(); position++) {
            index.put(normalizeHeader(headers.get(position)), position);
        }
        return index;
    }

    private String getValue(List<String> values, Map<String, Integer> headerIndex, String header) {
        Integer position = headerIndex.get(normalizeHeader(header));
        if (position == null || position >= values.size()) {
            return "";
        }
        return values.get(position).trim();
    }

    private String normalizeHeader(String value) {
        return value == null ? "" : value.replace("\uFEFF", "").trim();
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private LocalDateTime parseDateTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return LocalDateTime.parse(value.trim(), CSV_DATE_TIME);
        } catch (Exception exception) {
            return null;
        }
    }

    private double parseDouble(String value) {
        if (value == null || value.isBlank()) {
            return 0.0;
        }
        try {
            return Double.parseDouble(value.trim());
        } catch (NumberFormatException exception) {
            return 0.0;
        }
    }

    private String readNextDataLine(BufferedReader reader) throws IOException {
        String line;
        while ((line = reader.readLine()) != null) {
            if (!line.trim().isEmpty()) {
                return line;
            }
        }
        return null;
    }

    private List<String> parseCsvLine(String line) {
        List<String> values = new ArrayList<>();
        StringBuilder currentValue = new StringBuilder();
        boolean insideQuotes = false;

        for (int index = 0; index < line.length(); index++) {
            char currentCharacter = line.charAt(index);
            if (currentCharacter == '"') {
                boolean escapedQuote = insideQuotes
                        && index + 1 < line.length()
                        && line.charAt(index + 1) == '"';
                if (escapedQuote) {
                    currentValue.append('"');
                    index++;
                } else {
                    insideQuotes = !insideQuotes;
                }
            } else if (currentCharacter == ',' && !insideQuotes) {
                values.add(currentValue.toString().trim());
                currentValue.setLength(0);
            } else {
                currentValue.append(currentCharacter);
            }
        }

        values.add(currentValue.toString().trim());
        return values;
    }
}
