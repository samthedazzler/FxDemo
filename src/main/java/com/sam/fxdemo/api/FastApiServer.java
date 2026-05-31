package com.sam.fxdemo.api;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

public class FastApiServer implements AutoCloseable {
    private static final Path PROJECT_ROOT = Path.of("").toAbsolutePath();
    private static final Path EMBEDDED_PYTHON =
            PROJECT_ROOT
                    .resolve("backend")
                    .resolve("python")
                    .resolve("python.exe");

    private final FastApiClient client = new FastApiClient();
    private Process process;

    public void start() throws IOException {
        if (isRunning()) {
            return;
        }

        ProcessBuilder processBuilder = new ProcessBuilder(
                resolvePythonCommand(),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000"
        );
        processBuilder.directory(
                PROJECT_ROOT.resolve("backend").toFile()
        );
        processBuilder.environment().put("PYTHONPATH",
                PROJECT_ROOT.resolve("backend").resolve("server").toAbsolutePath().toString() + ";" +
                PROJECT_ROOT.resolve("backend").resolve("server").resolve("packages").toAbsolutePath().toString()
        );
        processBuilder.redirectErrorStream(true);
        processBuilder.redirectOutput(ProcessBuilder.Redirect.appendTo(PROJECT_ROOT.resolve("fastapi.log").toFile()));

        process = processBuilder.start();
    }

    public boolean waitUntilHealthy(Duration timeout) {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            if (isHealthy()) {
                return true;
            }

            if (process != null && !process.isAlive()) {
                return false;
            }

            try {
                Thread.sleep(250);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                return false;
            }
        }

        return false;
    }

    public boolean isHealthy() {
        try {
            return client.isHealthy();
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            return false;
        }
    }

    @Override
    public void close() {
        if (process == null || !process.isAlive()) {
            return;
        }

        process.destroy();
        try {
            if (!process.waitFor(3, java.util.concurrent.TimeUnit.SECONDS)) {
                process.destroyForcibly();
            }
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            process.destroyForcibly();
        }
    }

    private boolean isRunning() {
        return process != null && process.isAlive();
    }

    private String resolvePythonCommand() {

        if (Files.isRegularFile(EMBEDDED_PYTHON)) {
            return EMBEDDED_PYTHON.toString();
        }

        throw new RuntimeException(
                "Embedded Python not found: "
                        + EMBEDDED_PYTHON
        );
    }
}
