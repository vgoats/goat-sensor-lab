package com.vgoats.sensorlab

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SaveAlt
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.vgoats.sensorlab.domain.IngestiveBehavior
import com.vgoats.sensorlab.domain.Placement
import com.vgoats.sensorlab.domain.PostureActivity
import com.vgoats.sensorlab.domain.Species
import com.vgoats.sensorlab.domain.SensorSourceType
import com.vgoats.sensorlab.domain.WelfareState
import java.util.Locale
import kotlin.math.sqrt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SensorLabApp(viewModel: SensorLabViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { viewModel.refreshSensorAvailability() }

    fun selectSource(sourceType: SensorSourceType) {
        viewModel.setSensorSource(sourceType)
        if (sourceType == SensorSourceType.XIAO_NRF52840_SENSE && !context.hasBlePermissions()) {
            permissionLauncher.launch(requiredBlePermissions())
        }
    }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Scaffold(
                topBar = { TopAppBar(title = { Text("Goat Sensor Lab") }) },
                snackbarHost = { SnackbarHost(snackbarHostState) },
            ) { padding ->
                SensorLabScreen(
                    state = state,
                    viewModel = viewModel,
                    onShare = { viewModel.shareLastSession(context) },
                    onSourceSelected = ::selectSource,
                    modifier = Modifier.padding(padding),
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SensorLabScreen(
    state: SensorLabUiState,
    viewModel: SensorLabViewModel,
    onShare: () -> Unit,
    onSourceSelected: (SensorSourceType) -> Unit,
    modifier: Modifier = Modifier,
) {
    val sessionActive = state.preparing || state.recording
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionTitle("Session")
        Text("Sensor source", style = MaterialTheme.typography.labelLarge)
        ChoiceRow(
            values = SensorSourceType.entries,
            selected = state.sensorSourceType,
            label = { it.displayName() },
            enabled = !sessionActive,
            onSelected = onSourceSelected,
        )
        if (state.sensorSourceType == SensorSourceType.XIAO_NRF52840_SENSE) {
            OutlinedTextField(
                value = state.boardDeviceId,
                onValueChange = viewModel::setBoardDeviceId,
                label = { Text("XIAO board ID") },
                supportingText = { Text("Printed at boot, for example GoatSensor-1A2B3C4D5E6F7788") },
                enabled = !sessionActive,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        OutlinedTextField(
            value = state.animalId,
            onValueChange = viewModel::setAnimalId,
            label = { Text("Animal ID") },
            enabled = !sessionActive,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        ChoiceRow(
            values = Species.entries,
            selected = state.species,
            label = { it.name.lowercase().replaceFirstChar(Char::uppercase) },
            enabled = !sessionActive,
            onSelected = viewModel::setSpecies,
        )
        OutlinedTextField(
            value = state.annotatorId,
            onValueChange = viewModel::setAnnotatorId,
            label = { Text("Annotator ID") },
            enabled = !sessionActive,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.shedId,
            onValueChange = viewModel::setShedId,
            label = { Text("Shed / pen ID") },
            enabled = !sessionActive,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.cameraIds,
            onValueChange = viewModel::setCameraIds,
            label = { Text("Camera IDs") },
            supportingText = { Text("Comma-separated IDs used for synchronized observation") },
            enabled = !sessionActive,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Text("Placement", style = MaterialTheme.typography.labelLarge)
        ChoiceRow(
            values = Placement.entries,
            selected = state.placement,
            label = { it.displayName() },
            enabled = !sessionActive,
            onSelected = viewModel::setPlacement,
        )
        Text("Sampling rate", style = MaterialTheme.typography.labelLarge)
        ChoiceRow(
            values = when (state.sensorSourceType) {
                SensorSourceType.ANDROID_PHONE -> SensorLabViewModel.PHONE_RATES
                SensorSourceType.XIAO_NRF52840_SENSE -> SensorLabViewModel.XIAO_RATES
            },
            selected = state.sampleRateHz,
            label = { "$it Hz" },
            enabled = !sessionActive,
            onSelected = viewModel::setSampleRate,
        )
        OutlinedTextField(
            value = state.notes,
            onValueChange = viewModel::setNotes,
            label = { Text("Session notes") },
            enabled = !sessionActive,
            minLines = 2,
            modifier = Modifier.fillMaxWidth(),
        )

        HorizontalDivider()
        SectionTitle("Sensor Status")
        Text(state.sensorDescription, style = MaterialTheme.typography.bodyMedium)
        LiveValues(state)

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(
                onClick = if (sessionActive) viewModel::stopRecording else viewModel::startRecording,
                modifier = Modifier.weight(1f),
            ) {
                Icon(
                    imageVector = if (sessionActive) Icons.Default.Stop else Icons.Default.PlayArrow,
                    contentDescription = null,
                )
                Text(
                    when {
                        state.preparing -> "Cancel"
                        state.recording -> "Stop"
                        else -> "Start"
                    },
                )
            }
            OutlinedButton(onClick = onShare, enabled = !sessionActive) {
                Icon(Icons.Default.SaveAlt, contentDescription = "Export last session")
                Text("Export")
            }
        }

        if (state.recording) {
            HorizontalDivider()
            SectionTitle("Live Labels")
            Text("Ingestive behavior", style = MaterialTheme.typography.labelLarge)
            ChoiceRow(
                values = IngestiveBehavior.entries,
                selected = state.labels.ingestive,
                label = { it.displayName() },
                onSelected = viewModel::setIngestive,
            )
            Text("Posture and activity", style = MaterialTheme.typography.labelLarge)
            ChoiceRow(
                values = PostureActivity.entries,
                selected = state.labels.postureActivity,
                label = { it.displayName() },
                onSelected = viewModel::setPosture,
            )
            Text("Welfare observation", style = MaterialTheme.typography.labelLarge)
            ChoiceRow(
                values = WelfareState.entries,
                selected = state.labels.welfare,
                label = { it.displayName() },
                onSelected = viewModel::setWelfare,
            )
            FilterChip(
                selected = state.labels.invalidData,
                onClick = { viewModel.setInvalidData(!state.labels.invalidData) },
                label = { Text("Invalid / obstructed data") },
            )
            Spacer(Modifier.height(12.dp))
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun <T> ChoiceRow(
    values: List<T>,
    selected: T,
    label: (T) -> String,
    enabled: Boolean = true,
    onSelected: (T) -> Unit,
) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        values.forEach { value ->
            FilterChip(
                selected = value == selected,
                onClick = { onSelected(value) },
                enabled = enabled,
                label = { Text(label(value)) },
            )
        }
    }
}

@Composable
private fun LiveValues(state: SensorLabUiState) {
    val frame = state.latestFrame
    val magnitude = frame?.let {
        sqrt(
            it.accelerationXMs2 * it.accelerationXMs2 +
                it.accelerationYMs2 * it.accelerationYMs2 +
                it.accelerationZMs2 * it.accelerationZMs2,
        )
    }
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(
            when {
                state.preparing -> "Connecting; no samples recorded yet"
                state.recording -> "Recording (requested ${state.sampleRateHz} Hz)"
                else -> "Ready"
            },
            fontWeight = FontWeight.SemiBold,
            color = if (state.recording) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        )
        Text("Samples: ${state.sampleCount}")
        Text("Acceleration: ${magnitude?.format(3) ?: "-"} m/s²")
        Text(
            "Gyroscope: ${frame?.gyroscopeXRadS?.format(3) ?: "-"}, " +
                "${frame?.gyroscopeYRadS?.format(3) ?: "-"}, " +
                "${frame?.gyroscopeZRadS?.format(3) ?: "-"} rad/s",
        )
        state.lastSessionName?.let { Text("Last session: $it") }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
}

private fun Double.format(decimals: Int): String = String.format(Locale.US, "%.${decimals}f", this)

private fun Enum<*>.displayName(): String = name
    .lowercase()
    .split('_')
    .joinToString(" ") { it.replaceFirstChar(Char::uppercase) }

private fun SensorSourceType.displayName(): String = when (this) {
    SensorSourceType.ANDROID_PHONE -> "Phone IMU"
    SensorSourceType.XIAO_NRF52840_SENSE -> "XIAO Sense (BLE)"
}

private fun requiredBlePermissions(): Array<String> = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
} else {
    arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
}

private fun android.content.Context.hasBlePermissions(): Boolean = requiredBlePermissions().all {
    ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
}
