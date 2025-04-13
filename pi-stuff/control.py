import smbus
import time
import RPi.GPIO as GPIO

# I2C configuration
I2C_BUS_NUMBER = 1             # For Raspberry Pi, bus 1 is typical for I2C.
DEVICE_ADDRESS = 0x10          # Change this to your motor controller's I2C address.

# Motor controller register addresses (example values)
MOTOR_SPEED_REGISTER = 0x01    # Hypothetical register for speed
MOTOR_DIRECTION_REGISTER = 0x02  # Hypothetical register for direction

# Optional: GPIO configuration (for extra control, such as motor enable)
MOTOR_ENABLE_PIN = 17          # Example GPIO pin number used for enable

def init_gpio():
    """
    Initializes GPIO settings. For many I2C devices on the Raspberry Pi,
    the SDA and SCL lines are managed by the OS. This function is useful
    if you need additional GPIO control (like an enable/disable pin).
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MOTOR_ENABLE_PIN, GPIO.OUT)
    # Enable motor controller (logic level may depend on your hardware)
    GPIO.output(MOTOR_ENABLE_PIN, GPIO.HIGH)

def cleanup_gpio():
    """Clean up GPIO settings."""
    GPIO.cleanup()

def set_motor_speed(bus, speed):
    """
    Sets the motor speed by writing a value to the motor controller.
    The speed value is constrained between 0 and 255.
    
    :param bus: An instance of smbus.SMBus.
    :param speed: Desired speed (0-255).
    """
    speed = max(0, min(255, speed))
    bus.write_byte_data(DEVICE_ADDRESS, MOTOR_SPEED_REGISTER, speed)

def set_motor_direction(bus, direction):
    """
    Sets the motor direction.
    For this example, the convention is:
        0 - forward
        1 - reverse
    
    :param bus: An instance of smbus.SMBus.
    :param direction: Direction value (0 or 1).
    """
    if direction not in (0, 1):
        raise ValueError("Direction must be 0 (forward) or 1 (reverse).")
    bus.write_byte_data(DEVICE_ADDRESS, MOTOR_DIRECTION_REGISTER, direction)

def main():
    # Initialize any necessary GPIOs.
    init_gpio()
    
    # Create an I2C bus instance
    bus = smbus.SMBus(I2C_BUS_NUMBER)
    
    try:
        # Example: set motor direction to forward (0)
        set_motor_direction(bus, 0)
        
        # Ramp up motor speed gradually
        for speed in range(0, 256, 10):
            print(f"Setting speed to {speed}")
            set_motor_speed(bus, speed)
            time.sleep(0.1)  # Adjust delay as necessary
        
        # Ramp down motor speed gradually
        for speed in range(255, -1, -10):
            print(f"Setting speed to {speed}")
            set_motor_speed(bus, speed)
            time.sleep(0.1)
    
    except Exception as e:
        print("An error occurred:", e)
    
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    main()
