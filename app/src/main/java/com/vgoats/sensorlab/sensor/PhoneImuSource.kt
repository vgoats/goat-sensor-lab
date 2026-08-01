package com.vgoats.sensorlab.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

class PhoneImuSource(context: Context) : SensorSource, SensorEventListener {
    private val applicationContext = context.applicationContext
    private val sensorManager = applicationContext.getSystemService(SensorManager::class.java)
    private val batteryManager = applicationContext.getSystemService(BatteryManager::class.java)
    private val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val sequence = AtomicLong(0)
    private val installationId = resolveInstallationId(
        existing = applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
            .getString(INSTALLATION_ID_KEY, null),
        create = { UUID.randomUUID().toString() },
        persist = { created ->
            applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(INSTALLATION_ID_KEY, created)
                .commit()
        },
    )
    private val stableDeviceId = "AndroidPhone-$installationId"
    private val gyroscopeSamples = GyroscopeSampleBuffer()

    private var sensorThread: HandlerThread? = null
    private var callback: ((SensorFrame) -> Unit)? = null
    private var cachedBatteryPercent: Int? = null
    private var batteryReadAtNs = 0L
    private var activeSampleRateHz: Int? = null

    override val type = SensorSourceType.ANDROID_PHONE

    override val verifiedMetadata: SensorSourceMetadata
        get() = SensorSourceMetadata(
            deviceIdentity = stableDeviceId,
            sensorModel = buildString {
                append(accelerometer?.name ?: "accelerometer-unavailable")
                append(" + ")
                append(gyroscope?.name ?: "gyroscope-unavailable")
            },
            supportedRatesHz = SUPPORTED_RATES,
            activeRateHz = activeSampleRateHz,
            sampleReadMode = "accelerometer_with_preceding_gyro_within_tolerance",
            rawCapabilities = sensorMetadataDescription(),
            timeSyncMethod = "android_sensor_event_elapsed_realtime",
        )

    override val availability: SensorAvailability
        get() = when {
            accelerometer == null -> SensorAvailability(false, "Accelerometer unavailable")
            gyroscope == null -> SensorAvailability(true, "Accelerometer ready; gyroscope unavailable")
            else -> SensorAvailability(
                true,
                "${accelerometer.name} + ${gyroscope.name}",
            )
        }

    override fun start(
        sampleRateHz: Int,
        targetDeviceId: String?,
        onFrame: (SensorFrame) -> Unit,
        onStatus: (String) -> Unit,
        onReady: () -> Unit,
        onError: (String) -> Unit,
    ): Result<Unit> = runCatching {
        check(accelerometer != null) { "This phone does not have an accelerometer" }
        stop()
        callback = onFrame
        sequence.set(0)
        gyroscopeSamples.reset(gyroscopeToleranceForRateNs(sampleRateHz))
        cachedBatteryPercent = null
        batteryReadAtNs = 0L
        activeSampleRateHz = sampleRateHz.coerceIn(1, 200)

        val thread = HandlerThread("goat-sensor-imu").also { it.start() }
        sensorThread = thread
        val handler = Handler(thread.looper)
        val samplingPeriodUs = (1_000_000 / sampleRateHz.coerceIn(1, 200)).coerceAtLeast(5_000)

        val accelRegistered = sensorManager.registerListener(
            this,
            accelerometer,
            samplingPeriodUs,
            0,
            handler,
        )
        check(accelRegistered) { "Unable to register accelerometer listener" }
        gyroscope?.let {
            sensorManager.registerListener(this, it, samplingPeriodUs, 0, handler)
        }
        onReady()
        onStatus("Phone IMU recording")
    }

    override fun stop() {
        sensorManager.unregisterListener(this)
        callback = null
        sensorThread?.quitSafely()
        sensorThread = null
        activeSampleRateHz = null
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_GYROSCOPE -> {
                gyroscopeSamples.observe(event.timestamp, event.values.copyOf(3))
            }
            Sensor.TYPE_ACCELEROMETER -> emitAccelerometerFrame(event)
        }
    }

    private fun emitAccelerometerFrame(event: SensorEvent) {
        val gyro = gyroscopeSamples.preceding(event.timestamp)
        if (event.timestamp - batteryReadAtNs >= BATTERY_REFRESH_NS || cachedBatteryPercent == null) {
            cachedBatteryPercent = batteryManager
                .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                .takeIf { it in 0..100 }
            batteryReadAtNs = event.timestamp
        }
        callback?.invoke(
            SensorFrame(
                source = type,
                deviceId = stableDeviceId,
                sequence = sequence.getAndIncrement(),
                wallTimeEpochMs = System.currentTimeMillis(),
                monotonicTimeNs = event.timestamp,
                gyroscopeTimeNs = gyro?.timestampNs,
                accelerationXMs2 = event.values[0].toDouble(),
                accelerationYMs2 = event.values[1].toDouble(),
                accelerationZMs2 = event.values[2].toDouble(),
                gyroscopeXRadS = gyro?.values?.get(0)?.toDouble(),
                gyroscopeYRadS = gyro?.values?.get(1)?.toDouble(),
                gyroscopeZRadS = gyro?.values?.get(2)?.toDouble(),
                batteryPercent = cachedBatteryPercent,
            ),
        )
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    private fun sensorMetadataDescription(): String = listOfNotNull(
        "manufacturer=${Build.MANUFACTURER}",
        "model=${Build.MODEL}",
        accelerometer?.let {
            "accelerometer=${it.vendor}/${it.name};version=${it.version};resolution=${it.resolution};" +
                "max_range=${it.maximumRange};min_delay_us=${it.minDelay}"
        },
        gyroscope?.let {
            "gyroscope=${it.vendor}/${it.name};version=${it.version};resolution=${it.resolution};" +
                "max_range=${it.maximumRange};min_delay_us=${it.minDelay}"
        },
    ).joinToString(" | ")

    companion object {
        private const val BATTERY_REFRESH_NS = 60_000_000_000L
        private const val PREFERENCES_NAME = "phone_sensor_identity"
        private const val INSTALLATION_ID_KEY = "installation_uuid"
        private val SUPPORTED_RATES = listOf(5, 10, 16, 25, 50)
    }
}

internal data class TimedGyroscopeSample(
    val timestampNs: Long,
    val values: FloatArray,
)

internal class GyroscopeSampleBuffer(
    private var toleranceNs: Long = DEFAULT_GYRO_TOLERANCE_NS,
) {
    private val samples = mutableListOf<TimedGyroscopeSample>()

    fun reset(newToleranceNs: Long = toleranceNs) {
        require(newToleranceNs > 0) { "Gyroscope tolerance must be positive" }
        toleranceNs = newToleranceNs
        samples.clear()
    }

    fun observe(timestampNs: Long, values: FloatArray) {
        require(values.size >= 3) { "Gyroscope sample must contain three axes" }
        val sample = TimedGyroscopeSample(timestampNs, values.copyOf(3))
        val found = samples.binarySearchBy(timestampNs) { it.timestampNs }
        if (found >= 0) {
            samples[found] = sample
        } else {
            samples.add(-found - 1, sample)
        }
        while (samples.size > MAX_BUFFERED_GYRO_SAMPLES) samples.removeAt(0)
    }

    fun preceding(accelerationTimestampNs: Long): TimedGyroscopeSample? {
        var low = 0
        var high = samples.lastIndex
        var matchIndex = -1
        while (low <= high) {
            val middle = (low + high).ushr(1)
            if (samples[middle].timestampNs <= accelerationTimestampNs) {
                matchIndex = middle
                low = middle + 1
            } else {
                high = middle - 1
            }
        }
        if (matchIndex < 0) return null
        val match = samples[matchIndex]
        return match.takeIf { accelerationTimestampNs - it.timestampNs <= toleranceNs }
    }

    private companion object {
        const val DEFAULT_GYRO_TOLERANCE_NS = 250_000_000L
        const val MAX_BUFFERED_GYRO_SAMPLES = 128
    }
}

internal fun gyroscopeToleranceForRateNs(sampleRateHz: Int): Long =
    (3_000_000_000L / sampleRateHz.coerceIn(1, 200)).coerceIn(100_000_000L, 750_000_000L)

internal fun resolveInstallationId(
    existing: String?,
    create: () -> String,
    persist: (String) -> Boolean,
): String {
    val stored = existing?.trim()?.takeIf { value ->
        runCatching { UUID.fromString(value) }.isSuccess
    }
    if (stored != null) return stored.lowercase()
    val created = create().trim().also { UUID.fromString(it) }.lowercase()
    check(persist(created)) { "Unable to persist phone installation identity" }
    return created
}
