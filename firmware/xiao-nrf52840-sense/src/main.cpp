#include <Arduino.h>
#include <bluefruit.h>
#include <LSM6DS3.h>
#include <math.h>
#include <nrf.h>

namespace {
#ifndef GOAT_SENSOR_PROTOCOL_VERSION
#error "GOAT_SENSOR_PROTOCOL_VERSION must be supplied by the build configuration"
#endif
#define GOAT_SENSOR_STRINGIFY_INNER(value) #value
#define GOAT_SENSOR_STRINGIFY(value) GOAT_SENSOR_STRINGIFY_INNER(value)

constexpr char SERVICE_UUID[] = "7c1e0001-6b1b-4d4f-9d1a-c9986f217c10";
constexpr char CAPABILITIES_UUID[] = "7c1e0002-6b1b-4d4f-9d1a-c9986f217c10";
constexpr char CONTROL_UUID[] = "7c1e0003-6b1b-4d4f-9d1a-c9986f217c10";
constexpr char STREAM_UUID[] = "7c1e0004-6b1b-4d4f-9d1a-c9986f217c10";
constexpr char STATUS_UUID[] = "7c1e0005-6b1b-4d4f-9d1a-c9986f217c10";
constexpr char TIME_ANCHOR_UUID[] = "7c1e0006-6b1b-4d4f-9d1a-c9986f217c10";

constexpr uint8_t PROTOCOL_VERSION = GOAT_SENSOR_PROTOCOL_VERSION;
static_assert(PROTOCOL_VERSION == 2, "Firmware implements BLE Sensor Protocol v2");
constexpr uint16_t DEFAULT_SAMPLE_RATE_HZ = 26;

BLEService sensorService(SERVICE_UUID);
BLECharacteristic capabilitiesCharacteristic(CAPABILITIES_UUID);
BLECharacteristic controlCharacteristic(CONTROL_UUID);
BLECharacteristic streamCharacteristic(STREAM_UUID);
BLECharacteristic statusCharacteristic(STATUS_UUID);
BLECharacteristic timeAnchorCharacteristic(TIME_ANCHOR_UUID);

LSM6DS3 imu(I2C_MODE, 0x6A);

struct __attribute__((packed)) ImuPacket {
  uint32_t sequence;
  uint32_t boardUptimeMs;
  int16_t accelerationMilliG[3];
  int16_t gyroscopeCentiDegreesPerSecond[3];
};
static_assert(sizeof(ImuPacket) == 20, "IMU packet must fit the default BLE payload");

struct __attribute__((packed)) TimeAnchorPacket {
  uint8_t version;
  uint8_t flags;
  uint16_t reserved;
  uint32_t sequence;
  uint32_t boardUptimeMs;
};

struct __attribute__((packed)) StatusPacket {
  uint8_t version;
  uint8_t flags;
  uint16_t sampleRateHz;
  uint32_t droppedSamples;
};

bool streamingEnabled = false;
uint16_t sampleRateHz = DEFAULT_SAMPLE_RATE_HZ;
uint32_t sequenceNumber = 0;
uint32_t droppedSamples = 0;
uint32_t nextSampleUs = 0;
uint32_t nextStatusMs = 0;
char deviceName[28] = {};

void sendStatus();

void connectCallback(uint16_t) {
  streamingEnabled = false;
  sendStatus();
}

void disconnectCallback(uint16_t, uint8_t) {
  streamingEnabled = false;
  sendStatus();
}

int16_t saturatingRound(float value) {
  if (value > 32767.0f) return 32767;
  if (value < -32768.0f) return -32768;
  return static_cast<int16_t>(lroundf(value));
}

void sendStatus() {
  StatusPacket status{
      PROTOCOL_VERSION,
      static_cast<uint8_t>(streamingEnabled ? 1U : 0U),
      sampleRateHz,
      droppedSamples};
  statusCharacteristic.write(&status, sizeof(status));
  if (Bluefruit.connected()) statusCharacteristic.notify(&status, sizeof(status));
}

void sendTimeAnchor() {
  const uint32_t boardUptimeMs = millis();
  TimeAnchorPacket anchor{PROTOCOL_VERSION, 0, 0, sequenceNumber, boardUptimeMs};
  timeAnchorCharacteristic.write(&anchor, sizeof(anchor));
  if (Bluefruit.connected()) timeAnchorCharacteristic.notify(&anchor, sizeof(anchor));
}

void controlWriteCallback(
    uint16_t,
    BLECharacteristic*,
    uint8_t* data,
    uint16_t length) {
  if (length < 1) return;
  streamingEnabled = data[0] != 0;
  if (length >= 3) {
    const uint16_t requestedRate = static_cast<uint16_t>(data[1]) |
                                   (static_cast<uint16_t>(data[2]) << 8U);
    if (requestedRate == 13 || requestedRate == 26) sampleRateHz = requestedRate;
  }
  nextSampleUs = micros();
  nextStatusMs = millis() + 5000UL;
  sendTimeAnchor();
  sendStatus();
}

void configureBle() {
  snprintf(
      deviceName,
      sizeof(deviceName),
      "GoatSensor-%08lX%08lX",
      static_cast<unsigned long>(NRF_FICR->DEVICEID[1]),
      static_cast<unsigned long>(NRF_FICR->DEVICEID[0]));
  Bluefruit.begin();
  Bluefruit.Periph.setConnectCallback(connectCallback);
  Bluefruit.Periph.setDisconnectCallback(disconnectCallback);
  Bluefruit.setTxPower(0);
  Bluefruit.setName(deviceName);

  sensorService.begin();

  capabilitiesCharacteristic.setProperties(CHR_PROPS_READ);
  capabilitiesCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  capabilitiesCharacteristic.setMaxLen(220);
  capabilitiesCharacteristic.begin();
  char capabilities[220] = {};
  snprintf(
      capabilities,
      sizeof(capabilities),
      "{\"protocol\":" GOAT_SENSOR_STRINGIFY(GOAT_SENSOR_PROTOCOL_VERSION)
      ",\"firmware\":\"0.2.0\",\"device_id\":\"%s\","
      "\"imu\":\"LSM6DS3TR-C\",\"rates_hz\":[13,26],\"accel_g\":4,"
      "\"gyro_dps\":500,\"packet_bytes\":20,"
      "\"sample_read\":\"sequential_axes\"}",
      deviceName);
  capabilitiesCharacteristic.write(capabilities, strlen(capabilities));

  controlCharacteristic.setProperties(CHR_PROPS_WRITE | CHR_PROPS_WRITE_WO_RESP);
  controlCharacteristic.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
  controlCharacteristic.setFixedLen(3);
  controlCharacteristic.setWriteCallback(controlWriteCallback);
  controlCharacteristic.begin();

  streamCharacteristic.setProperties(CHR_PROPS_NOTIFY);
  streamCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  streamCharacteristic.setFixedLen(sizeof(ImuPacket));
  streamCharacteristic.begin();

  statusCharacteristic.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
  statusCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  statusCharacteristic.setFixedLen(sizeof(StatusPacket));
  statusCharacteristic.begin();

  timeAnchorCharacteristic.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
  timeAnchorCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  timeAnchorCharacteristic.setFixedLen(sizeof(TimeAnchorPacket));
  timeAnchorCharacteristic.begin();

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(sensorService);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 160);
  Bluefruit.Advertising.setFastTimeout(0);
  Bluefruit.Advertising.start(0);
}

void configureImu() {
  imu.settings.accelRange = 4;
  imu.settings.accelSampleRate = 26;
  imu.settings.gyroRange = 500;
  imu.settings.gyroSampleRate = 26;
  if (imu.begin() != 0) {
    Serial.println("IMU initialization failed");
    while (true) delay(1000);
  }
}

void sampleAndNotify() {
  const uint32_t nowMs = millis();

  ImuPacket packet{};
  packet.sequence = sequenceNumber++;
  packet.boardUptimeMs = nowMs;
  packet.accelerationMilliG[0] = saturatingRound(imu.readFloatAccelX() * 1000.0f);
  packet.accelerationMilliG[1] = saturatingRound(imu.readFloatAccelY() * 1000.0f);
  packet.accelerationMilliG[2] = saturatingRound(imu.readFloatAccelZ() * 1000.0f);
  packet.gyroscopeCentiDegreesPerSecond[0] = saturatingRound(imu.readFloatGyroX() * 100.0f);
  packet.gyroscopeCentiDegreesPerSecond[1] = saturatingRound(imu.readFloatGyroY() * 100.0f);
  packet.gyroscopeCentiDegreesPerSecond[2] = saturatingRound(imu.readFloatGyroZ() * 100.0f);

  if (!streamCharacteristic.notify(&packet, sizeof(packet))) droppedSamples++;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(250);
  configureImu();
  configureBle();
  sendStatus();
  Serial.print("Board ID: ");
  Serial.println(deviceName);
}

void loop() {
  if (!streamingEnabled || !Bluefruit.connected()) {
    delay(20);
    return;
  }

  const uint32_t nowUs = micros();
  const uint32_t intervalUs = 1000000UL / sampleRateHz;
  if (static_cast<int32_t>(nowUs - nextSampleUs) >= 0) {
    const uint32_t lateIntervals = (nowUs - nextSampleUs) / intervalUs;
    if (lateIntervals > 0) {
      droppedSamples += lateIntervals;
      sequenceNumber += lateIntervals;
      nextSampleUs += lateIntervals * intervalUs;
    }
    nextSampleUs += intervalUs;
    sampleAndNotify();
  }
  const uint32_t nowMs = millis();
  if (static_cast<int32_t>(nowMs - nextStatusMs) >= 0) {
    nextStatusMs += 5000UL;
    sendStatus();
  }
}
