package com.vgoats.sensorlab.sensor

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.os.SystemClock
import androidx.core.content.ContextCompat
import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import java.util.UUID

/** BLE adapter for the Goat Sensor Lab firmware, not for HCBB82 vendor tags. */
class XiaoBleSource(context: Context) : SensorSource {
    private val applicationContext = context.applicationContext
    private val bluetoothManager = applicationContext.getSystemService(BluetoothManager::class.java)
    private val adapter: BluetoothAdapter? = bluetoothManager?.adapter

    private var scannerActive = false
    private var gatt: BluetoothGatt? = null
    private var onFrame: ((SensorFrame) -> Unit)? = null
    private var onStatus: ((String) -> Unit)? = null
    private var onReady: (() -> Unit)? = null
    private var onError: ((String) -> Unit)? = null
    private var targetDeviceId: String? = null
    private var selectedDeviceId: String? = null
    private var requestedRateHz = 26
    private var latestRssiDbm: Int? = null
    private var anchor: TimeAnchor? = null
    private var capabilities: XiaoCapabilities? = null
    private var latestDeviceStatus: XiaoStatus? = null
    private var streamStarted = false
    private var controlWritePending = false
    private var controlWriteConfirmed = false
    private var statusConfirmed = false
    private var controlRequestedMonotonicNs: Long? = null
    private var timeSyncUncertaintyNs: Long? = null
    private val sequenceTracker = UnsignedSequenceTracker()
    private var previousSampleTimeNs: Long? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private val scanTimeout = Runnable { handleScanTimeout() }
    private val handshakeTimeout = Runnable { fail("XIAO handshake did not complete within 15 seconds") }

    override val type = SensorSourceType.XIAO_NRF52840_SENSE

    override val verifiedMetadata: SensorSourceMetadata?
        get() {
            val observedCapabilities = capabilities ?: return null
            val identity = selectedDeviceId ?: return null
            return observedCapabilities.toMetadata(
                identity,
                latestDeviceStatus,
                timeSyncUncertaintyNs,
                sequenceTracker.totalMissing,
            )
        }

    override val availability: SensorAvailability
        get() = when {
            adapter == null -> SensorAvailability(false, "Bluetooth is unavailable")
            adapter.isEnabled.not() -> SensorAvailability(false, "Turn on Bluetooth")
            !hasPermissions() -> SensorAvailability(false, "Bluetooth permission required")
            else -> SensorAvailability(true, "Ready to scan for a GoatSensor board ID")
        }

    @SuppressLint("MissingPermission")
    override fun start(
        sampleRateHz: Int,
        targetDeviceId: String?,
        onFrame: (SensorFrame) -> Unit,
        onStatus: (String) -> Unit,
        onReady: () -> Unit,
        onError: (String) -> Unit,
    ): Result<Unit> = runCatching {
        check(availability.available) { availability.description }
        stop()
        this.onFrame = onFrame
        this.onStatus = onStatus
        this.onReady = onReady
        this.onError = onError
        this.targetDeviceId = GoatSensorIdentity.normalize(checkNotNull(targetDeviceId) { "XIAO board ID is required" })
            .also { check(it.isNotBlank()) { "XIAO board ID is required" } }
        selectedDeviceId = null
        requestedRateHz = if (sampleRateHz <= 13) 13 else 26
        capabilities = null
        latestDeviceStatus = null
        streamStarted = false
        controlWritePending = false
        controlWriteConfirmed = false
        statusConfirmed = false
        controlRequestedMonotonicNs = null
        timeSyncUncertaintyNs = null
        sequenceTracker.reset()
        previousSampleTimeNs = null
        onStatus("Scanning for GoatSensor-${this.targetDeviceId}")

        val scanner = checkNotNull(adapter?.bluetoothLeScanner) { "BLE scanner unavailable" }
        val filter = ScanFilter.Builder().setServiceUuid(ParcelUuid(SERVICE_UUID)).build()
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanner.startScan(listOf(filter), settings, scanCallback)
        scannerActive = true
        mainHandler.postDelayed(scanTimeout, SCAN_TIMEOUT_MS)
    }

    @SuppressLint("MissingPermission")
    override fun stop() {
        mainHandler.removeCallbacks(scanTimeout)
        mainHandler.removeCallbacks(handshakeTimeout)
        if (hasPermissions() && scannerActive) {
            adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        }
        scannerActive = false
        onFrame = null
        onStatus = null
        onReady = null
        onError = null
        targetDeviceId = null
        selectedDeviceId = null
        gatt?.disconnect()
        gatt?.close()
        gatt = null
        anchor = null
        capabilities = null
        latestDeviceStatus = null
        streamStarted = false
        controlWritePending = false
        controlWriteConfirmed = false
        statusConfirmed = false
        controlRequestedMonotonicNs = null
        timeSyncUncertaintyNs = null
        sequenceTracker.reset()
        previousSampleTimeNs = null
        latestRssiDbm = null
    }

    @SuppressLint("MissingPermission")
    private fun connect(result: ScanResult, advertisedDeviceId: String) {
        if (!scannerActive) return
        if (scannerActive) adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        scannerActive = false
        mainHandler.removeCallbacks(scanTimeout)
        latestRssiDbm = result.rssi
        selectedDeviceId = advertisedDeviceId
        onStatus?.invoke("Connecting to $advertisedDeviceId")
        mainHandler.postDelayed(handshakeTimeout, HANDSHAKE_TIMEOUT_MS)
        gatt = result.device.connectGatt(
            applicationContext,
            false,
            gattCallback,
            android.bluetooth.BluetoothDevice.TRANSPORT_LE,
        )
    }

    private fun hasPermissions(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            return ContextCompat.checkSelfPermission(
                applicationContext,
                Manifest.permission.ACCESS_FINE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED
        }
        return ContextCompat.checkSelfPermission(
            applicationContext,
            Manifest.permission.BLUETOOTH_SCAN,
        ) == PackageManager.PERMISSION_GRANTED && ContextCompat.checkSelfPermission(
            applicationContext,
            Manifest.permission.BLUETOOTH_CONNECT,
        ) == PackageManager.PERMISSION_GRANTED
    }

    @SuppressLint("MissingPermission")
    private fun handleScanTimeout() {
        if (!scannerActive) return
        if (hasPermissions()) adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        scannerActive = false
        fail("${GoatSensorIdentity.advertisedName(targetDeviceId.orEmpty())} not found within 15 seconds")
    }

    private fun fail(message: String) {
        mainHandler.removeCallbacks(scanTimeout)
        mainHandler.removeCallbacks(handshakeTimeout)
        val callback = onError ?: return
        onError = null
        onStatus?.invoke(message)
        callback(message)
    }

    private val scanCallback = object : ScanCallback() {
        @SuppressLint("MissingPermission")
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val advertisedName = result.scanRecord?.deviceName ?: result.device.name ?: return
            if (GoatSensorIdentity.matches(targetDeviceId.orEmpty(), advertisedName)) {
                connect(result, GoatSensorIdentity.advertisedName(advertisedName))
            }
        }

        override fun onScanFailed(errorCode: Int) {
            scannerActive = false
            mainHandler.removeCallbacks(scanTimeout)
            fail("BLE scan failed ($errorCode)")
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        @SuppressLint("MissingPermission")
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("XIAO connection failed ($status)")
                return
            }
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    onStatus?.invoke("Discovering XIAO sensor service")
                    gatt.discoverServices()
                }
                BluetoothProfile.STATE_DISCONNECTED -> fail("XIAO disconnected")
            }
        }

        @SuppressLint("MissingPermission")
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("XIAO service discovery failed")
                return
            }
            val service = gatt.getService(SERVICE_UUID)
            val capabilitiesCharacteristic = service?.getCharacteristic(CAPABILITIES_UUID)
            val anchorCharacteristic = service?.getCharacteristic(TIME_ANCHOR_UUID)
            val streamCharacteristic = service?.getCharacteristic(STREAM_UUID)
            val statusCharacteristic = service?.getCharacteristic(STATUS_UUID)
            val controlCharacteristic = service?.getCharacteristic(CONTROL_UUID)
            if (
                capabilitiesCharacteristic == null || anchorCharacteristic == null ||
                streamCharacteristic == null || statusCharacteristic == null || controlCharacteristic == null
            ) {
                fail("Goat Sensor Lab BLE service not found")
                return
            }
            onStatus?.invoke("Verifying XIAO capabilities")
            if (!gatt.readCharacteristic(capabilitiesCharacteristic)) {
                fail("Unable to read XIAO capabilities")
            }
        }

        @SuppressLint("MissingPermission")
        override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("Unable to enable XIAO notifications")
                return
            }
            val service = gatt.getService(SERVICE_UUID) ?: return
            when (descriptor.characteristic.uuid) {
                TIME_ANCHOR_UUID -> enableNotifications(gatt, service.getCharacteristic(STREAM_UUID))
                STREAM_UUID -> enableNotifications(gatt, service.getCharacteristic(STATUS_UUID))
                STATUS_UUID -> {
                    val statusCharacteristic = service.getCharacteristic(STATUS_UUID)
                    if (!gatt.readCharacteristic(statusCharacteristic)) {
                        fail("Unable to read XIAO status")
                    }
                }
            }
        }

        @Deprecated("Used on Android 12 and earlier")
        @Suppress("DEPRECATION")
        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int,
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                handleCharacteristic(gatt, characteristic.uuid, characteristic.value ?: byteArrayOf())
            } else if (characteristic.uuid == CAPABILITIES_UUID || characteristic.uuid == STATUS_UUID) {
                fail("Unable to read required XIAO metadata")
            }
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
            status: Int,
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                handleCharacteristic(gatt, characteristic.uuid, value)
            } else if (characteristic.uuid == CAPABILITIES_UUID || characteristic.uuid == STATUS_UUID) {
                fail("Unable to read required XIAO metadata")
            }
        }

        @Deprecated("Used on Android 12 and earlier")
        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            handleCharacteristic(gatt, characteristic.uuid, characteristic.value ?: byteArrayOf())
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
        ) = handleCharacteristic(gatt, characteristic.uuid, value)

        override fun onReadRemoteRssi(gatt: BluetoothGatt, rssi: Int, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) latestRssiDbm = rssi
        }

        override fun onCharacteristicWrite(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int,
        ) {
            if (characteristic.uuid != CONTROL_UUID) return
            controlWritePending = false
            if (status != BluetoothGatt.GATT_SUCCESS) {
                fail("XIAO rejected the stream command ($status)")
                return
            }
            controlWriteConfirmed = true
            maybeReady()
        }
    }

    @SuppressLint("MissingPermission")
    private fun handleCharacteristic(gatt: BluetoothGatt, uuid: UUID, value: ByteArray) {
        when (uuid) {
            CAPABILITIES_UUID -> {
                runCatching {
                    val identity = checkNotNull(selectedDeviceId) { "XIAO identity is unavailable" }
                    XiaoCapabilities.parse(value).also { it.validate(requestedRateHz, identity) }
                }.onSuccess { observed ->
                    capabilities = observed
                    val service = gatt.getService(SERVICE_UUID)
                    val anchorCharacteristic = service?.getCharacteristic(TIME_ANCHOR_UUID)
                    if (anchorCharacteristic == null) {
                        fail("XIAO time-anchor characteristic missing")
                    } else {
                        enableNotifications(gatt, anchorCharacteristic)
                    }
                }.onFailure { fail("Invalid XIAO capabilities: ${it.message}") }
            }
            STATUS_UUID -> {
                runCatching { XiaoStatus.decode(value) }
                    .onSuccess { observed ->
                        latestDeviceStatus = observed
                        if (!controlWritePending && !controlWriteConfirmed) {
                            writeControl(gatt)
                        } else if (observed.streaming) {
                            if (observed.sampleRateHz != requestedRateHz) {
                                fail(
                                    "XIAO reported ${observed.sampleRateHz} Hz after " +
                                        "requesting $requestedRateHz Hz",
                                )
                            } else {
                                statusConfirmed = true
                                maybeReady()
                            }
                        }
                    }
                    .onFailure { fail("Invalid XIAO status: ${it.message}") }
            }
            TIME_ANCHOR_UUID -> {
                runCatching { XiaoPacketDecoder.decodeTimeAnchor(value) }
                    .onSuccess { boardAnchor ->
                        val receivedNs = SystemClock.elapsedRealtimeNanos()
                        val sentNs = controlRequestedMonotonicNs ?: receivedNs
                        val roundTripNs = (receivedNs - sentNs).coerceAtLeast(0L)
                        val midpointNs = sentNs + roundTripNs / 2L
                        timeSyncUncertaintyNs = roundTripNs / 2L
                        anchor = TimeAnchor(
                            wallTimeEpochMs = System.currentTimeMillis() - (roundTripNs / 2L) / 1_000_000L,
                            monotonicTimeNs = midpointNs,
                            boardUptimeMs = boardAnchor.boardUptimeMs,
                            nextSequence = boardAnchor.sequence,
                        )
                        sequenceTracker.expectNext(boardAnchor.sequence)
                        maybeReady()
                    }
                    .onFailure { fail("Invalid XIAO time anchor: ${it.message}") }
            }
            STREAM_UUID -> {
                if (!streamStarted) return
                val currentAnchor = anchor ?: return
                val currentDeviceId = selectedDeviceId ?: return
                runCatching {
                    XiaoPacketDecoder.decode(
                        bytes = value,
                        deviceId = currentDeviceId,
                        anchorWallTimeEpochMs = currentAnchor.wallTimeEpochMs,
                        anchorMonotonicTimeNs = currentAnchor.monotonicTimeNs,
                        anchorBoardUptimeMs = currentAnchor.boardUptimeMs,
                        rssiDbm = latestRssiDbm,
                    )
                }.onSuccess { frame ->
                    if (
                        previousSampleTimeNs == null &&
                        unsignedDelta(frame.sourceUptimeMs ?: 0L, currentAnchor.boardUptimeMs) >
                        MAX_INITIAL_ANCHOR_DELTA_MS
                    ) {
                        fail("First XIAO sample is too far from the fresh time anchor")
                        return@onSuccess
                    }
                    val sequence = sequenceTracker.observe(frame.sequence)
                    if (!sequence.accepted) {
                        onStatus?.invoke("Ignored duplicate or out-of-order XIAO packet ${frame.sequence}")
                        return@onSuccess
                    }
                    val priorTime = previousSampleTimeNs
                    if (priorTime != null && frame.monotonicTimeNs <= priorTime) {
                        fail("XIAO sample clock moved backward")
                        return@onSuccess
                    }
                    previousSampleTimeNs = frame.monotonicTimeNs
                    onFrame?.invoke(frame)
                    if (frame.sequence % (requestedRateHz * 5L) == 0L) {
                        gatt.readRemoteRssi()
                        onStatus?.invoke(
                            "XIAO streaming at $requestedRateHz Hz; missing packets: ${sequence.totalMissing}",
                        )
                    }
                }.onFailure { onStatus?.invoke("Invalid XIAO packet: ${it.message}") }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun enableNotifications(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
        if (!gatt.setCharacteristicNotification(characteristic, true)) {
            fail("Unable to enable ${characteristic.uuid}")
            return
        }
        val descriptor = characteristic.getDescriptor(CCCD_UUID)
        if (descriptor == null) {
            fail("Notification descriptor missing for ${characteristic.uuid}")
            return
        }
        val accepted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gatt.writeDescriptor(
                descriptor,
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE,
            ) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            @Suppress("DEPRECATION")
            gatt.writeDescriptor(descriptor)
        }
        if (!accepted) {
            fail("Unable to write notification descriptor for ${characteristic.uuid}")
        }
    }

    @SuppressLint("MissingPermission")
    private fun writeControl(gatt: BluetoothGatt) {
        val characteristic = gatt.getService(SERVICE_UUID)?.getCharacteristic(CONTROL_UUID) ?: return
        val value = byteArrayOf(1, (requestedRateHz and 0xff).toByte(), (requestedRateHz ushr 8).toByte())
        controlRequestedMonotonicNs = SystemClock.elapsedRealtimeNanos()
        val accepted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gatt.writeCharacteristic(
                characteristic,
                value,
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT,
            ) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            characteristic.value = value
            @Suppress("DEPRECATION")
            characteristic.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            @Suppress("DEPRECATION")
            gatt.writeCharacteristic(characteristic)
        }
        if (accepted) {
            controlWritePending = true
            onStatus?.invoke("Waiting for XIAO to confirm stream start")
        } else {
            fail("Unable to start XIAO stream")
        }
    }

    private fun maybeReady() {
        if (
            streamStarted || capabilities == null || !controlWriteConfirmed ||
            !statusConfirmed || anchor == null
        ) return
        streamStarted = true
        mainHandler.removeCallbacks(handshakeTimeout)
        onReady?.invoke()
        onReady = null
        onStatus?.invoke("XIAO streaming at $requestedRateHz Hz")
    }

    private data class TimeAnchor(
        val wallTimeEpochMs: Long,
        val monotonicTimeNs: Long,
        val boardUptimeMs: Long,
        @Suppress("unused") val nextSequence: Long,
    )

    private fun unsignedDelta(value: Long, origin: Long): Long = (value - origin) and 0xffffffffL

    companion object {
        val SERVICE_UUID: UUID = UUID.fromString("7c1e0001-6b1b-4d4f-9d1a-c9986f217c10")
        val CAPABILITIES_UUID: UUID = UUID.fromString("7c1e0002-6b1b-4d4f-9d1a-c9986f217c10")
        val CONTROL_UUID: UUID = UUID.fromString("7c1e0003-6b1b-4d4f-9d1a-c9986f217c10")
        val STREAM_UUID: UUID = UUID.fromString("7c1e0004-6b1b-4d4f-9d1a-c9986f217c10")
        val STATUS_UUID: UUID = UUID.fromString("7c1e0005-6b1b-4d4f-9d1a-c9986f217c10")
        val TIME_ANCHOR_UUID: UUID = UUID.fromString("7c1e0006-6b1b-4d4f-9d1a-c9986f217c10")
        private val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        private const val SCAN_TIMEOUT_MS = 15000L
        private const val HANDSHAKE_TIMEOUT_MS = 15000L
        private const val MAX_INITIAL_ANCHOR_DELTA_MS = 10000L

    }
}
