package com.sam.fxdemo.api;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

public class FastApiClient {
    private static final URI HEALTH_URI = URI.create("http://127.0.0.1:8000/health");

    private final HttpClient httpClient;

    public FastApiClient() {
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
    }

    public boolean isHealthy() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(HEALTH_URI)
                .timeout(Duration.ofSeconds(2))
                .GET()
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        return response.statusCode() == 200 && response.body().contains("\"status\":\"ok\"");
    }
}
