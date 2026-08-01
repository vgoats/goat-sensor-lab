package com.vgoats.sensorlab.domain

data class SensorFrame(
    val schemaVersion: Int = 1,
    val source: SensorSourceType,
    val deviceId: String,
    val sequence: Long,
    val wallTimeEpochMs: Long,
    val monotonicTimeNs: Long,
    val sourceUptimeMs: Long? = null,
    val gyroscopeTimeNs: Long?,
    val accelerationXMs2: Double,
    val accelerationYMs2: Double,
    val accelerationZMs2: Double,
    val gyroscopeXRadS: Double?,
    val gyroscopeYRadS: Double?,
    val gyroscopeZRadS: Double?,
    val temperatureC: Double? = null,
    val batteryPercent: Int? = null,
    val rssiDbm: Int? = null,
)

enum class SensorSourceType {
    ANDROID_PHONE,
    XIAO_NRF52840_SENSE,
}

enum class Species {
    GOAT,
    SHEEP,
}

enum class Placement {
    PHONE_HANDHELD_TEST,
    NECK_COLLAR,
    EAR_MOUNT,
    BODY_HARNESS,
}

enum class IngestiveBehavior {
    UNKNOWN,
    FEEDING,
    RUMINATION,
    NEITHER,
}

enum class PostureActivity {
    UNKNOWN,
    LYING,
    STANDING,
    ACTIVE_MOVEMENT,
}

enum class WelfareState {
    UNKNOWN,
    NORMAL,
    SUSPECTED_ABNORMAL_INACTIVITY,
}

data class BehaviorLabels(
    val ingestive: IngestiveBehavior = IngestiveBehavior.UNKNOWN,
    val postureActivity: PostureActivity = PostureActivity.UNKNOWN,
    val welfare: WelfareState = WelfareState.UNKNOWN,
    val invalidData: Boolean = false,
)

data class SessionConfig(
    val animalId: String,
    val species: Species,
    val placement: Placement,
    val sampleRateHz: Int,
    val notes: String,
    val source: SensorSourceType,
    val expectedDeviceId: String?,
    val annotatorId: String,
    val shedId: String,
    val cameraIds: String,
    val sourceDeviceMetadata: Map<String, String> = emptyMap(),
)
