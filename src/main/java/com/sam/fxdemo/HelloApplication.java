package com.sam.fxdemo;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Scene;
import javafx.stage.Stage;
import com.sam.fxdemo.api.FastApiServer;

import java.io.IOException;
import java.time.Duration;

public class HelloApplication extends Application {
    private final FastApiServer fastApiServer = new FastApiServer();

    @Override
    public void start(Stage stage) throws IOException {
        try {
            fastApiServer.start();
            fastApiServer.waitUntilHealthy(Duration.ofSeconds(8));
        } catch (IOException exception) {
            System.err.println("Unable to start FastAPI: " + exception.getMessage());
        }

        // Loads the table layout from the resources/views folder.
        FXMLLoader fxmlLoader = new FXMLLoader(HelloApplication.class.getResource("views/hello-view.fxml"));

        // Creates a wider scene for all 3 documented operational modules.
        Scene scene = new Scene(fxmlLoader.load(), 1500, 820);
        scene.getStylesheets().add(
                HelloApplication.class.getResource("views/dashboard.css").toExternalForm()
        );

        // Shows the dashboard scope from the operations documentation.
        stage.setTitle("WFM Dashboard - Modules 1-3");

        // Attaches the scene to the JavaFX stage.
        stage.setScene(scene);

        // Opens the application window.
        stage.show();
    }

    @Override
    public void stop() {
        fastApiServer.close();
    }
}
