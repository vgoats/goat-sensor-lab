package com.vgoats.sensorlab.sensor

internal object GoatSensorIdentity {
    fun normalize(value: String): String = value
        .trim()
        .uppercase()
        .removePrefix("GOATSENSOR-")

    fun advertisedName(targetId: String): String = "GoatSensor-${normalize(targetId)}"

    fun matches(targetId: String, advertisedName: String): Boolean =
        normalize(targetId).isNotBlank() && normalize(advertisedName) == normalize(targetId)
}

internal data class SequenceObservation(
    val accepted: Boolean,
    val missingSincePrevious: Long,
    val totalMissing: Long,
)

internal class UnsignedSequenceTracker {
    private var previous: Long? = null
    var totalMissing: Long = 0
        private set

    fun reset() {
        previous = null
        totalMissing = 0
    }

    fun expectNext(sequence: Long) {
        previous = ((sequence and UINT32_MASK) - 1L) and UINT32_MASK
        totalMissing = 0
    }

    fun observe(sequence: Long): SequenceObservation {
        val normalized = sequence and UINT32_MASK
        val prior = previous
        if (prior == null) {
            previous = normalized
            return SequenceObservation(true, 0, totalMissing)
        }
        val delta = (normalized - prior) and UINT32_MASK
        if (delta == 0L || delta > MAX_FORWARD_DELTA) {
            return SequenceObservation(false, 0, totalMissing)
        }
        val missing = delta - 1
        totalMissing += missing
        previous = normalized
        return SequenceObservation(true, missing, totalMissing)
    }

    private companion object {
        const val UINT32_MASK = 0xffffffffL
        const val MAX_FORWARD_DELTA = 0x7fffffffL
    }
}
