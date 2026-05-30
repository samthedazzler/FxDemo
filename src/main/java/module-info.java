module com.sam.fxdemo {
    requires javafx.controls;
    requires javafx.fxml;
    requires java.net.http;
    requires eu.hansolo.medusa;
    requires io.fair_acc.chartfx;
    requires io.fair_acc.dataset;


    opens com.sam.fxdemo to javafx.fxml;
    exports com.sam.fxdemo;
}
