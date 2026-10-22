package dev.apktester.behemoth.services;

import android.printservice.PrintJob;
import android.printservice.PrintService;
import android.printservice.PrinterDiscoverySession;

/**
 * Fixture de registro/deteccao de servico de sistema (A1): estende
 * PrintService para o RustyDroid validar o componente declarado no
 * manifesto (permissao BIND_PRINT_SERVICE).
 *
 * onCreatePrinterDiscoverySession devolve null por construcao (sessao de
 * descoberta nunca e aberta nesta fase); onPrintJobQueued e o segundo
 * metodo abstrato da superclasse e permanece vazio.
 */
public class PrintStub extends PrintService {

    @Override
    protected PrinterDiscoverySession onCreatePrinterDiscoverySession() {
        return null;
    }

    @Override
    protected void onRequestCancelPrintJob(PrintJob printJob) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }

    @Override
    protected void onPrintJobQueued(PrintJob printJob) {
        // Sem processamento: fixture de registro/deteccao do manifesto.
    }
}
