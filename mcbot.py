from javascript import require, On, Once, AsyncTask, once, off
from simple_chalk import chalk
from utils.vec3_conversion import vec3_to_str
import threading
import time
from environs import Env
env = Env()
env.read_env()

# Import the javascript libraries
mineflayer = require("mineflayer")
mineflayer_pathfinder = require("mineflayer-pathfinder")
vec3 = require("vec3")

# Global bot parameters

server_host = env.str("server")
server_port = 25565
reconnect = True
bot_password = env.str("password")
bot_suffix = env.str("name_suffix")


class MCBot:

    def __init__(self, bot_name):
        self.bot_args = {
            "host": server_host,
            "port": server_port,
            "username": bot_name,
            "password": bot_password,
            "hideErrors": False,
        }
        self.reconnect = reconnect
        self.bot_name = bot_name
        self.attacking = False
        self.attack_thread = None
        self.start_bot()

    # Tags bot username before console messages
    def log(self, message):
        print(f"[{self.bot.username}] {message}")

    def pathfind_to_goal(self, goal_location):
        try:
            self.bot.pathfinder.setGoal(
                mineflayer_pathfinder.pathfinder.goals.GoalNear(
                    goal_location["x"], goal_location["y"], goal_location["z"], 1
                )
            )
        except Exception as e:
            self.log(f"Error while trying to run pathfind_to_goal: {e}")

    # Check if bot has a sword in inventory
    def has_sword(self):
        try:
            # Get all items from inventory
            items = self.bot.inventory.items()
            
            # Check for any sword type
            sword_types = ["wooden_sword", "stone_sword", "iron_sword", "golden_sword", "diamond_sword", "netherite_sword"]
            
            for item in items:
                if item.name in sword_types:
                    self.log(chalk.green(f"Found {item.name} in inventory"))
                    return True
            
            self.log(chalk.red("No sword found in inventory"))
            return False
        except Exception as e:
            self.log(chalk.red(f"Error checking for sword: {e}"))
            return False

    # Equip the best available sword
    def equip_sword(self):
        try:
            # Priority order for swords (best to worst)
            sword_priority = ["netherite_sword", "diamond_sword", "iron_sword", "golden_sword", "stone_sword", "wooden_sword"]
            
            items = self.bot.inventory.items()
            best_sword = None
            
            # Find the best available sword
            for sword_type in sword_priority:
                for item in items:
                    if item.name == sword_type:
                        best_sword = item
                        break
                if best_sword:
                    break
            
            if best_sword:
                # Equip the sword
                self.bot.equip(best_sword, "hand")
                self.log(chalk.green(f"Equipped {best_sword.name}"))
                return True
            else:
                self.log(chalk.red("No sword available to equip"))
                return False
        except Exception as e:
            self.log(chalk.red(f"Error equipping sword: {e}"))
            return False

    # Start mineflayer bot
    def start_bot(self):
        self.bot = mineflayer.createBot(self.bot_args)
        self.bot.loadPlugin(mineflayer_pathfinder.pathfinder)
        self.start_events()

    # Attach mineflayer events to bot
    def start_events(self):

        # Login event
        @On(self.bot, "login")
        def login(this):
            self.bot_socket = self.bot._client.socket
            self.log(
                chalk.green(
                    f"Logged in to {self.bot_socket.server if self.bot_socket.server else self.bot_socket._host }"
                )
            )

        @On(self.bot, "death")
        def death(this):
            self.log(chalk.red("Bot has died. Respawning..."))
            try:
                self.bot.emit("respawn")  # Trigger respawn immediately
                print("Respawning...")
            except Exception as e:
                self.log(chalk.red(f"Error while trying to respawn: {e}"))
        
        # Kicked event
        @On(self.bot, "kicked")
        def kicked(this, reason, loggedIn):
            if loggedIn:
                self.log(chalk.redBright(f"Kicked whilst trying to connect: {reason}"))

        # Chat event
        @On(self.bot, "messagestr")
        def messagestr(this, message, messagePosition, jsonMsg, sender, verified=None):
            
            if "Use the command" in message:
                if "register" in message:
                    self.bot.chat(f"/register {bot_password} {bot_password}")
                    self.log(chalk.green("Registering..."))
                elif "login" in message:
                    self.bot.chat(f"/login {bot_password}")
                    self.log(chalk.green("Logging in..."))
            
            try:
                sender_name = message.split()[0].strip("<>")
            
                if sender_name == "UnknownGC" or "RankedRooky":
                    
                    # Quit command
                    if messagePosition == "chat" and "quit" in message:
                        self.reconnect = False
                        this.quit()
                        
                    # Boat command
                    elif messagePosition == "chat" and "boat" in message.lower():
                        self.log(chalk.yellow(f"Boat command received from {sender_name}, attempting to ride a nearby boat..."))
                        self.ride_boat()
                        
                    # Attack command
                    elif messagePosition == "chat" and "attack" in message.lower():
                        self.start_attacking()

                    # Stop command
                    elif messagePosition == "chat" and "stop" in message.lower():
                        self.stop_attacking()
                    
                    # Come command
                    elif "come" in message:
                        position = self.bot.entity.position
                        print(f"Current position: {position}")
                        local_players = self.bot.players
                        for el in local_players:
                            player_data = local_players[el]
                            if player_data["uuid"] == sender:
                                vec3_temp = local_players[el].entity.position
                                player_location = vec3(
                                    vec3_temp["x"], vec3_temp["y"] + 1, vec3_temp["z"]
                                )

                        if player_location:
                            self.log(
                                chalk.magenta(
                                    f"Pathfinding to player at {vec3_to_str(player_location)}"
                                )
                            )
                            self.pathfind_to_goal(player_location)
                        else:
                            self.log(f"Player not found.")
            except:
                pass

        # End event
        @On(self.bot, "end")
        def end(this, reason):
            self.log(chalk.red(f"Disconnected: {reason}"))
            self.stop_attacking()

            # Reconnect
            if self.reconnect:
                self.log(chalk.cyanBright("Attempting to reconnect"))
                self.start_bot()

    # Ride boat function
    def ride_boat(self):
        try:
            boat = self.bot.nearestEntity(lambda e: e.name == "boat")
            if boat:
                self.log(chalk.green("Found a boat nearby, attempting to ride it..."))
                try:
                    self.bot.activateEntity(boat, timeout=10000)
                except Exception as e:
                    self.log(chalk.red(f"Failed to ride the boat: {e}"))
            else:
                self.log(chalk.red("No boat nearby, unable to ride."))
        except:
            pass

    # Start attacking Breeze mob
    def start_attacking(self):
        if self.attacking:
            self.log(chalk.yellow("Already attacking."))
            return

        # Check if bot has a sword before starting attack
        if not self.has_sword():
            self.log(chalk.red("Cannot start attacking: No sword found in inventory!"))
            return
        
        # Try to equip the best available sword
        if not self.equip_sword():
            self.log(chalk.red("Cannot start attacking: Failed to equip sword!"))
            return

        self.attacking = True
        self.attack_thread = threading.Thread(target=self.attack_loop)
        self.attack_thread.start()
        self.log(chalk.green("Started attacking Breeze mobs."))

    # Attack loop
    def attack_loop(self):
        while self.attacking:
            # Check if we still have a sword equipped before each attack
            if not self.has_sword():
                self.log(chalk.red("Sword lost! Stopping attack."))
                self.attacking = False
                break
            
            # Find the closest valid target each loop
            target = self.find_breeze_mob()
            
            try:
                if target and target.displayName == "Breeze":
                    try:
                        self.bot.attack(target)

                    except Exception as e:
                        self.log(chalk.red(f"Error while attacking: {e}"))

                time.sleep(1)
            except:
                pass

    # Stop attacking
    def stop_attacking(self):
        if self.attacking:
            self.attacking = False
            if self.attack_thread:
                self.attack_thread.join()
            self.log(chalk.red("Stopped attacking."))

    # Find the nearest Breeze mob
    def find_breeze_mob(self):
        # Find the nearest Breeze mob using nearestEntity
        try:
            breeze_mob = self.bot.nearestEntity(lambda e: e.name == "Breeze" and e.type == "mob")
            
            if breeze_mob:
                return breeze_mob
            else:
                self.log("No Breeze mob found.")
                return None
        except:
            pass
        
        


# Run function that starts the bot(s)
#bot1 = MCBot("AFK_BOT_1")
bot2 = MCBot(bot_suffix + "1")
bot3 = MCBot(bot_suffix + "2")
