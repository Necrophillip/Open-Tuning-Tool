import re
texts = [
    "Gyros detected: gyro 1: BMI270",
    "Gyro: ICM42688P",
    "Gyros detected: gyro 1: MPU6000",
    "MCU F405 Clock=168MHz\nGyros detected: gyro 1\n",
    "MCU F405 Clock=168MHz, Gyros detected: gyro 1: icm42688p, I2C:1",
]
r4 = re.compile(r"(BMI\d+|MPU\d+|ICM\d+|LSM\d+)[A-Za-z0-9\-]*", re.IGNORECASE)

for t in texts:
    m = r4.search(t)
    print(f"[{t.strip()}] -> r4: {m.group(0) if m else None}")
