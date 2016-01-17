import atexit, http.client, json, re, sys, threading, time, websocket
from datetime import datetime

class FinitClient:
	def __init__(self):
		self.user_data = None
		self.ws = None
		self.s = None
		self.lasst_error = None
		self.ws_timeout = 5
		atexit.register(self.logout)
		self.on_login = None
		self.on_logout = None
		self.on_message = None
		self.on_error = None
		self.custom_data = None
		self.user_id_cache = {}
		self.user_name_cache = {}
	def login(self, email, password):
		self.last_error = None
		try:
			conn = http.client.HTTPSConnection("finit.co", timeout=30)
			conn.request("POST", "/api/auth",
				body=json.dumps({"email": email, "password": password}),
				headers={"Content-Type": "application/json;charset=utf-8"})
			resp = conn.getresponse();
			user_data = json.loads(str(resp.readall(), "utf-8"))
			if "error" in user_data:
				self.last_error = user_data["error"]
				if self.on_login is not None: self.on_login(self, True)
				return False
		except Exception as e:
			self.last_error = e
			if self.on_login is not None: self.on_login(self, True)
			return False
		self.user_data = user_data
		self.user_id_cache[self.user_data["user"]["username"].upper()] = self.user_data["user"]["id"]
		self.user_name_cache[self.user_data["user"]["id"]] = self.user_data["user"]["username"]
		self.ws = websocket.WebSocketApp("wss://anvel.io/?authPath=%2Fapi%2Fwebsockets%2Fauth&instance_id=M7AdOTjPvJbBYKDU&token="+self.user_data["token"],
			on_message=self.on_ws_message)
		self.ws_connected = False
		self.ws.on_open = self.on_ws_connect
		self.ws_thread = threading.Thread(target=self.ws.run_forever)
		self.ws_thread.daemon = True
		self.ws_thread.start()
		timeout = self.ws_timeout
		while not self.ws_connected and timeout > 0:
			time.sleep(1)
			timeout -= 1
		if timeout == 0 and not self.ws.sock.connected:
			if self.on_login is not None: self.on_login(self, False)
			return False
		if self.on_login is not None: self.on_login(self, True)
		return True
	def logout(self):
		atexit.unregister(self.logout)
		self.ws_connected = False
		if self.user_data is not None:
			success = False
			try:
				conn = http.client.HTTPSConnection("finit.co", timeout=30)
				conn.request("DELETE", "/api/auth", body="[]",
					headers={"Content-Type": "text/plain; charset=UTF-8",
						"Authorization": "Bearer "+self.user_data['token']})
				resp = conn.getresponse()
				if str(resp.readall(), "utf-8").strip() == "Good":
					success = True
			except Exception as e:
				self.last_error = e
			self.user_data = None
			if self.on_logout is not None: self.on_logout(self, success)
			return success
		return None
	def wait_for_logout(self):
		self.logout()
		while self.user_data is not None:
			time.sleep(1)
	def send_json(self, data):
		self.ws.send(json.dumps(data))
	def on_ws_connect(self, ws):
		self.ws_connected = ws.sock.connected
	def on_ws_message(self, sock, message):
		try:
			data = json.loads(message)
			if (self.on_message is not None and data and "event" in data and
				data["event"] != "ping"):
				self.on_message(self, data)
		except Exception as e:
			if self.on_error is not None:
				self.on_error(self, e)
	def _internal_get_messages(self, channel):
		try:
			conn = http.client.HTTPSConnection("finit.co", timeout=30)
			conn.request("GET", "/api/messages?chatroom_channel={}".format(
				channel), headers={"Authorization": "Bearer "+self.user_data['token']})
			resp = json.loads(str(conn.getresponse().readall(), "utf-8"))
			return resp
		except Exception as e:
			print(e)
		return None
	def join(self, channel):
		if channel[0] == "@":
			return self._private_join(channel[1:])
		if channel[0] == "#":
			channel = channel[1:]
		self.send_json({"event":"subscribe", "channel":"pub_"+channel})
		return True
	def leave(self, channel):
		if channel[0] == "@":
			return self._private_leave(channel[1:])
		if channel[0] == "#":
			channel = channel[1:]
		self.send_json({"event":"unsubscribe", "channel":"pub_"+channel})
		return True
	def message(self, channel, message):
		if channel[0] == "@":
			return self._private_message(channel[1:], message)
		if channel[0] == "#":
			channel = channel[1:]
		self.send_json({"event":"client-message","channel":"pub_"+channel,"data":{"channel":"pub_"+channel,"body":message}})
		return True
	def get_messages(self, channel):
		if channel[0] == "@":
			return self._get_private_messages(channel[1:])
		if channel[0] == "#":
			channel = channel[1:]
		return self._internal_get_messages("pub_"+channel)
	def _get_ids_sorted(self, user):
		uid = self.get_user_id(user)
		if uid is None or self.user_data is None:
			return None, None
		if self.user_data["user"]["id"] < uid:
			id1 = self.user_data["user"]["id"]
			id2 = uid
		else:
			id1 = uid
			id2 = self.user_data["user"]["id"]
		return id1, id2
	def _private_join(self, user):
		id1, id2 = self._get_ids_sorted(user)
		if id1 is None:
			return False
		channel = "prv_{}_{}".format(id1, id2)
		self.send_json({"event":"subscribe", "channel":channel})
		return True
	def _private_leave(self, user):
		id1, id2 = self._get_ids_sorted(user)
		if id1 is None:
			return False
		channel = "prv_{}_{}".format(id1, id2)
		self.send_json({"event":"unsubscribe", "channel":channel})
		return True
	def _private_message(self, user, message):
		id1, id2 = self._get_ids_sorted(user)
		if id1 is None:
			return False
		channel = "prv_{}_{}".format(id1, id2)
		self.send_json({"event":"client-message","channel":channel,"data":{"channel":channel,"body":message}})
		return True
	def _get_private_messages(self, user):
		id1, id2 = self._get_ids_sorted(user)
		if id1 is None:
			return False
		channel = "prv_{}_{}".format(id1, id2)
		return self._internal_get_messages(channel)
	def get_user_info(self, username):
		try:
			conn = http.client.HTTPSConnection("finit.co", timeout=30)
			conn.request("GET", "/api/users/"+username,
				headers={"Authorization": "Bearer "+self.user_data['token']})
			resp = conn.getresponse()
			resp = json.loads(str(resp.readall(), "utf-8"))
			if "data" in resp and resp["data"] is None:
				return None
			if "id" not in resp["data"]:
				return None
			return resp
		except:
			pass
		return None
	def get_current_user(self):
		if self.user_data is None:
			return None, None
		return self.user_data["user"]["id"], self.user_data["user"]["username"]
	def get_user_id(self, username):
		if username.startswith("#"):
			return None
		if username.startswith("@"):
			username = username[1:]
		username_up = username.upper()
		if username_up in self.user_id_cache:
			return self.user_id_cache[username_up]
		uinfo = self.get_user_info(username)
		if not uinfo: return None
		self.user_id_cache[username_up] = uinfo["data"]["id"]
		self.user_name_cache[uinfo["data"]["id"]] = uinfo["data"]["username"]
		return uinfo["data"]["id"]
	def get_normalized_channel_name(self, channel):
		channel = channel.strip()
		if not channel.startswith("@") and not channel.startswith("#"):
			channel = "#" + channel
		if len(channel) == 1: return None
		return channel
	def get_channel_name(self, pub_prv_fmt):
		channel = pub_prv_fmt.strip()
		if channel.startswith("pub_"):
			return "#"+channel[4:]
		elif channel.startswith("prv_"):
			_, id1, id2 = channel.split("_")
			uid = int(id1 if self.user_data["user"]["id"] == int(id2) else id2)
			if uid in self.user_name_cache:
				return "@"+self.user_name_cache[uid]
		return channel
