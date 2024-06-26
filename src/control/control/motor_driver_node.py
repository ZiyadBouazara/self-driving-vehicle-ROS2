import math
import time
from typing import Tuple

import rclpy
import serial
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Empty

MAX_SPEED = 0.43  # in m/s
WHEEL_BASE = 0.13  # in m
MU = 0.38


def clamp(value: int, min_value: int, max_value: int):
    return max(min_value, min(value, max_value))


class MotorDriverNode(Node):
    def __init__(self):
        super().__init__("motor_driver_node", parameter_overrides=[])

        self.create_subscription(Twist, "cmd_vel", self.cmd_vel_callback, 10)

        self.create_subscription(Empty, "/reset_odom", self.reset_odom, 10)
        self.odom_pub = self.create_publisher(Twist, "odom", 10)

        self.odom_twist = Twist()
        self.reset_odom(None)

        self.get_logger().info("Motor driver node started")

    def reset_odom(self, msg):
        self.odom_twist.linear.x = 0.0
        self.odom_twist.linear.y = 0.0
        self.odom_twist.linear.z = 0.0

        self.odom_twist.angular.x = 0.0
        self.odom_twist.angular.y = 0.0
        self.odom_twist.angular.z = 0.0

        self.last_time = time.time()

        self.get_logger().info("Motor driver node started")

    def cmd_vel_callback(self, twist_msg):
        val_left, val_right = self.get_left_and_right_speed(twist_msg)

        json_command = self.create_json_command(val_left, val_right)
        ser = serial.Serial("/dev/esp32", baudrate=1000000)
        try:
            ser.write(json_command.encode())
        except:
            self.get_logger().error("Failed to send motor command")
            return

        self.publish_odom(twist_msg)

    def create_json_command(self, val_left: int, val_right: int):
        json_command = '{"T":1,"L":' + str(val_left) + ',"R":' + str(val_right) + "}"
        return json_command

    def get_left_and_right_speed(self, twist_msg) -> Tuple[int, int]:
        v_x = twist_msg.linear.x
        omega_z = twist_msg.angular.z

        if math.isnan(v_x) or math.isnan(omega_z):
            self.get_logger().warn("Received NaN values in Twist message. Doing nothing")
            return 0, 0

        if math.isinf(v_x) or math.isinf(omega_z):
            self.get_logger().warn("Received inf. values in Twist message. Doing nothing")
            return 0, 0

        v_left = v_x - omega_z * WHEEL_BASE / 2.0
        v_right = v_x + omega_z * WHEEL_BASE / 2.0

        byte_val_left = int(255.0 * v_left / MAX_SPEED)
        byte_val_right = int(255.0 * v_right / MAX_SPEED)

        if byte_val_left < -255 or byte_val_left > 255 or byte_val_right < -255 or byte_val_right > 255:
            self.get_logger().debug("Speed values exceed limits. Clamping values")

            byte_val_left = clamp(byte_val_left, -255, 255)
            byte_val_right = clamp(byte_val_right, -255, 255)

        return byte_val_left, byte_val_right

    def publish_odom(self, twist: Twist):
        current_time = time.time()
        dt = current_time - self.last_time

        # Translation
        self.odom_twist.linear.x += twist.linear.x * dt

        # Rotation
        self.odom_twist.angular.z += twist.angular.z * dt * MU

        self.odom_pub.publish(self.odom_twist)

        self.last_time = current_time


def main(args=None):
    rclpy.init(args=args)

    motor_driver_node = MotorDriverNode()

    rclpy.spin(motor_driver_node)

    motor_driver_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
