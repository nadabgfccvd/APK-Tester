package dev.apktester.behemoth.receivers;

import android.app.admin.DeviceAdminReceiver;

/**
 * Fixture de registro/deteccao de receiver (A1): estende
 * DeviceAdminReceiver e responde ao filtro
 * android.app.action.DEVICE_ADMIN_ENABLED declarado no manifesto.
 *
 * O manifesto NAO anexa meta-data de device-admin nesta fase (decisao da
 * A1): o receiver fica como fixture simples de componente, sem policies
 * ativas. Nenhum override e necessario (a superclasse nao tem metodos
 * abstratos).
 */
public class DeviceAdminReceiverStub extends DeviceAdminReceiver {
}
