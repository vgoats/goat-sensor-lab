# Security and responsible disclosure

Do not commit farm credentials, API keys, animal treatment records, staff details, raw video, or
precise farm locations. Exported sessions belong in access-controlled research storage, not Git.

Report a security issue privately to the VGoats maintainers rather than opening a public issue.
Include the affected version, reproduction steps, impact, and any proposed mitigation.

## BLE prototype boundary

The prototype XIAO nRF52840 Sense BLE GATT service is open and unauthenticated. It does not
currently require pairing or bonding, encrypt the GATT session, authorize individual devices, or
enforce a device allow-list. Any nearby BLE-capable device may be able to discover the service,
read its characteristics, receive sample notifications, or attempt the prototype control write.
Treat all prototype BLE data and commands as untrusted research traffic. Do not use this protocol
for production animal operations, sensitive farm data, or safety-critical control.

Before production deployment, the BLE and backend design must add, at minimum:

- LE Secure Connections pairing and bonding with authenticated, encrypted GATT access.
- An immutable per-device identity and server-side device allow-list; never trust a mutable display
  name or an unverified MAC address as authorization.
- Authorization for control writes, per-farm tenancy checks, replay protection, and key rotation or
  revocation when a device is lost.
- TLS for every gateway/mobile-to-backend connection, authenticated ingestion, least-privilege
  credentials, audit logs, retention limits, and an offline queue that does not silently lose
  samples.

The prototype has no automatic cloud upload. Exported sessions belong in access-controlled
research storage, not Git.
