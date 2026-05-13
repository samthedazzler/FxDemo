module com.sam.fxdemo {
    requires javafx.controls;
    requires javafx.fxml;
    requires java.net.http;


    opens com.sam.fxdemo to javafx.fxml;
    exports com.sam.fxdemo;
}
