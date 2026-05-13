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

        // Creates a wider scene so all CSV columns can be viewed comfortably.
        Scene scene = new Scene(fxmlLoader.load(), 1200, 650);

        // Shows a title that describes what this screen displays.
        stage.setTitle("CSV Data Table");

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
