#!/usr/bin/env python3

import re
from datetime import datetime
from finitclient import FinitClient
from getpass import getpass

def on_login(conn, success):
	if success:
		print("\033[1G * You are now logged in as", conn.user_data["user"]["username"])
	else:
		print("\033[1G * Failed to log in")

def on_logout(conn, success):
	if success:
		print("\033[1G * Succesfully logged out")
	else:
		print("\033[1G * Failed to log out, error:", conn.last_error)

def on_message(conn, data):
	if data["event"] == "connected":
		pass
	elif data["event"] == "subscribed":
		conn.custom_data = {
			"channel": conn.get_channel_name(data["channel"]),
			"members": []
		}
		for m in data["members"]:
			conn.custom_data["members"].append({"id":m["id"],"user":m["username"]})
		print("\033[1G * successfully joined {}".format(conn.custom_data["channel"]), end="\n> ")
	elif data["event"] == "unsubscribed":
		print("\033[1G * successfully left {}".format(conn.custom_data["channel"]), end="\n> ")
		conn.custom_data = None
	elif data["event"] == "subscription-failure":
		print("\033[1G * Failed to subscribe to channel")
	elif data["event"] == "client-message":
		channel = conn.get_channel_name(data["channel"])
		if channel.startswith("@"):
			print("\033[1G [PM] @{}: {}".format(
				data["data"]["sender"]["username"],
				data["data"]["body"]
			), end="\n> ")
		else:
			print("\033[1G {} @{}: {}".format(
				channel,
				data["data"]["sender"]["username"],
				data["data"]["body"]
			), end="\n> ")
	elif data["event"] == 10: # This is a PM notification (does not contain the actuall PM)
		#print("\033[1G *", data["event_info"])
		pass
	elif data["event"] == "member-added":
		m = data["data"]
		conn.custom_data["members"].append({"id":m["id"],"user":m["username"]})
		print("\033[1G *", m["username"], "has joined", end="\n> ")
	elif data["event"] == "member-removed":
		m = data["data"]
		to_remove = None
		for i in conn.custom_data["members"]:
			if i["id"] == m["id"]:
				to_remove = i
				break
		if to_remove is not None:
			conn.custom_data["members"].remove(to_remove)
		print("\033[1G *", m["username"], "has left", end="\n> ")
	elif data["event"] == "client-poll-posted":
		#print("\033[1G", data, end="\n> ")
		pass
	elif data["event"] == "client-vote":
		#print("\033[1G", data, end="\n> ")
		pass
	elif data["event"] == "client-connected":
		#print("\033[1G", data, end="\n> ")
		pass # useless, only for seeing which friends are online
	elif data["event"] == "client-disconnected":
		#{"event":"client-disconnected","userId":2052}
		#print("\033[1G", data, end="\n> ")
		pass # useless, only for seeing which friends are online
	else:
		# We didn't recognize this event
		#print("\033[1G", data, end="\n> ")
		pass

def on_error(conn, e):
	print("ERROR:", e)
	sys.exit()

if __name__ == "__main__":
	c = FinitClient()
	c.on_login = on_login
	c.on_message = on_message
	c.on_logout = on_logout
	c.on_error = on_error
	c.login(input("Email> "), getpass("Password> "))
	try:
		last_room = None
		while True:
			cmd = input("> ")
			orig_cmd = cmd
			cmd = cmd.strip().split(maxsplit=1)
			if len(cmd) > 0:
				cmd[0] = cmd[0].upper()
			if len(cmd) > 0 and cmd[0] == "/HELP":
				print("Available commands:")
				print(" /join #channel")
				print(" /join @user")
				print(" /leave")
				print(" /list")
				print(" /whois @user")
				print(" /exit")
				print("Anything else you type will be sent as a message")
			if len(cmd) == 1 and cmd[0] == "/LEAVE" and last_room is not None:
				c.leave(last_room)
				last_room = None
			elif len(cmd) == 2 and cmd[0] == "/JOIN":
				if last_room is not None:
					c.leave(last_room)
				c.join(cmd[1])
				last_room = cmd[1]
			elif len(cmd) == 1 and cmd[0] == "/LIST" and last_room is not None:
				if len(c.custom_data["members"]) == 0:
					print("There are no members in the channel #{}".format(
						c.custom_data["channel"]
					))
				else:
					print("Members of channel: #{}".format(c.custom_data["channel"]))
					for m in c.custom_data["members"]:
						print(" *", m["user"])
			elif len(cmd) == 2 and cmd[0] == "/WHOIS":
				info = c.get_user_info(cmd[1].strip())
				if info is None:
					print("\033[1G * No such user")
				else:
					if info["data"]["id"] == 1:
						mod_of = "everything, he's the admin"
					elif len(info["data"]["mod_powers"]) == 0:
						mod_of = "nothing"
					else:
						mod_of = ", ".join(["#"+re.match("^pub_(.*)",i).group(1) for i in info["data"]["mod_powers"]])
					print("\033[1G * ID: {}, is guest: {}, user: {}, website: {}, bio: {}, moderator of: {}".format(
						info["data"]["id"],
						"yes" if info["data"]["is_temp"] == 1 else "no",
						info["data"]["username"],
						info["data"]["website"] if len(info["data"]["website"]) else "none",
						info["data"]["bio"] if len(info["data"]["bio"]) else "none",
						mod_of
					))
			elif len(cmd) == 1 and cmd[0] == "/EXIT":
				c.wait_for_logout()
				break
			elif last_room is not None:
				orig_cmd = re.sub("^\/\/", "/", orig_cmd).strip()
				if len(orig_cmd) > 0:
					c.message(last_room, orig_cmd)
	except (KeyboardInterrupt, EOFError):
		pass
	c.wait_for_logout()
