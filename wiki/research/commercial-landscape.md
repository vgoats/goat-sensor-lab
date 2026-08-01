# Commercial Landscape

No listed product is independently validated for all desired outcomes in indoor goats and sheep. Product pages show availability or specifications; they do not establish model accuracy on our animals.

| Product | Publicly described capability | Fit for this project | Evidence status / unknowns |
|---|---|---|---|
| [Copernitech PLF Ear-Tag](https://www.copernitech.com/pages/products/eartags.php) / collar | Sheep/goat marketing; 6-axis IMU; 12/25/50 Hz; raw SD recording or averaged LoRaWAN data | Strongest visible research-hardware comparison | **Vendor specification**; battery, mount performance, and independent behavior validation unknown |
| [iFarmTec iEwe/iFlock](https://ifarmtec.pt/produtos.html) | Sheep/goat collar ecosystem using inertial/other sensing and gateway/cloud | Relevant commercial/research comparator | Product claims plus [indoor-sheep posture research](https://pmc.ncbi.nlm.nih.gov/articles/PMC8469024/) and [goat-kidding research](https://www.mdpi.com/2076-2615/13/1/120); raw access and broad external validation require confirmation |
| [Cowmed tested on ewes](https://pmc.ncbi.nlm.nih.gov/articles/PMC12944205/) | Cattle collar adapted to indoor/pasture sheep for feeding/rumination | Useful transfer benchmark | **Independent evidence**; feeding stronger than rumination, collar rotation affected results |
| [HerdDogg cattle ear tag tested on housed ewes](https://pmc.ncbi.nlm.nih.gov/articles/PMC8833334/) | Ear activity and temperature index | Shows cattle-device transfer can reveal activity changes | **Independent small case study**, but proprietary index, transfer failures, and lack of retained raw axes prevent direct reproduction |
| [Heatime cattle-derived collar tested on Alpine goats](https://agris.fao.org/search/en/providers/122439/records/66290d23dd0a5d0f21618ba8) | Activity-based estrus alerts | Demonstrates possible but variable estrus transfer | **Independent study**; synchronized estrus results were stronger than return-to-estrus detection; not a general breeding claim |
| RumiWatch research halter | Jaw pressure plus inertial sensing | Strong reference for feeding/rumination ground truth | **Independent evidence**; heavier/intrusive and unsuitable as direct product design |
| HCBB82 BLE ear tag | Vendor protocol exposes movement flag, steps, temperature, battery, and ID; no raw axes | Useful low-power identity/activity comparator | **Vendor specification**; cannot train our raw-IMU behavior pipeline and its temperature is not core temperature |
| Halter | Cattle GPS/behavior/virtual fencing platform | Business/system-design reference only | **Cattle-only vendor system**; not suitable hardware or validated model for goats/sheep |
| Digitanimal / Nofence | GPS-oriented livestock tracking/virtual fencing | Poor indoor stall-fed fit | GPS, grazing, and solar assumptions do not match the project |

## Supplier due-diligence checklist

Request a datasheet and sample data before purchase, then independently verify:

- actual raw `acc_x/y/z` and `gyro_x/y/z`, units, range, sample clock, and supported rates;
- whether “raw” means every sample or a vendor feature/index;
- local buffering, packet-loss indication, time synchronization, and API ownership;
- gateway protocol and ability to send to our own HTTPS/MQTT endpoint;
- battery chemistry/capacity and measured life at the proposed configuration;
- exact device plus attachment mass, dimensions, ingress rating test report, and breakaway design;
- ability to map BLE/device ID to existing RFID identity;
- firmware/API availability independent of vendor cloud;
- certifications, MOQ, white labeling, tooling ownership, warranty, and end-of-life supply.

Treat marketplace badges, “AI health,” “5-year battery,” and “IP68” as vendor claims until the exact configuration and reports are supplied and samples pass bench and animal-welfare testing.
