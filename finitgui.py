#!/usr/bin/env python3

import re, time, threading, traceback
import tkinter as tk
from datetime import datetime
from finitclient import FinitClient

# I "stole" this from StackOverflow
def utc2local(utc):
	epoch = time.mktime(utc.timetuple())
	offset = datetime.fromtimestamp(epoch) - datetime.utcfromtimestamp(epoch)
	return utc + offset

# This one is also from StackOverflow
def convert65536(s):
	#Converts a string with out-of-range characters in it into a string with codes in it.
	l=list(s);
	i=0;
	while i<len(l):
		o=ord(l[i]);
		if o>65535:
			l[i]="{"+str(o)+"ū}";
		i+=1;
	return "".join(l);
def parse65536(match):
	#This is a regular expression method used for substitutions in convert65536back()
	text=int(match.group()[1:-2]);
	if text>65535:
		return chr(text);
	else:
		return "ᗍ"+str(text)+"ūᗍ";
def convert65536back(s):
	#Converts a string with codes in it into a string with out-of-range characters in it
	while re.search(r"{\d\d\d\d\d+ū}", s)!=None:
		s=re.sub(r"{\d\d\d\d\d+ū}", parse65536, s);
	s=re.sub(r"ᗍ(\d\d\d\d\d+)ūᗍ", r"{\1ū}", s);
	return s;

class FinitPyLogin(tk.Frame):
	def __init__(self, master=None, on_login=None):
		tk.Frame.__init__(self, master)
		self.on_login = on_login
		self.grid(sticky=tk.N+tk.S+tk.E+tk.W)
		self.create_widgets()
	def create_widgets(self):
		top = self.winfo_toplevel()
		top.rowconfigure(0, weight=1)
		top.columnconfigure(0, weight=1)
		top.config(borderwidth=10)
		
		self.columnconfigure(1, weight=1)
		
		self.user_lbl = tk.Label(self, text="Email")
		self.user_lbl.grid(column=0, row=0, sticky=tk.W+tk.E)
		
		self.user = tk.Entry(self, width=35)
		self.user_var = tk.StringVar()
		self.user["textvariable"] = self.user_var
		self.user.grid(column=1, row=0, columnspan=2, sticky=tk.W+tk.E)
		
		self.pwd_lbl = tk.Label(self, text="Password")
		self.pwd_lbl.grid(column=0, row=1)
		
		self.pwd = tk.Entry(self, show="*")
		self.pwd_var = tk.StringVar()
		self.pwd["textvariable"] = self.pwd_var
		self.pwd.grid(column=1, row=1, columnspan=2, sticky=tk.W+tk.E)
		
		self.err_msg = tk.Label(self)
		self.err_msg.grid(column=0, row=2, columnspan=3)
		
		self.login = tk.Button(self, text="Sign in", command=self.sign_in)
		self.login.grid(column=1, row=3, sticky=tk.E)
		
		self.QUIT = tk.Button(self, text="Quit", command=self.master.destroy)
		self.QUIT.grid(column=2, row=3, sticky=tk.W+tk.E)
	def sign_in(self):
		self.set_error("")
		if self.on_login is not None:
			self.on_login(self.user_var.get(), self.pwd_var.get())
	def set_error(self, message):
		self.err_msg["text"] = message

class FiniyPyMain(tk.Frame):
	def __init__(self, master=None, conn=None):
		tk.Frame.__init__(self, master)
		self.conn = conn
		self.conn.on_message = self.on_message
		self.rooms = {}
		self.active_channel = ""
		self.new_msg_count = 0
		self.new_pm = False
		self.master.protocol("WM_DELETE_WINDOW", self.before_close)
		self.grid(sticky=tk.N+tk.S+tk.E+tk.W)
		self.create_widgets()
	def create_widgets(self):
		top = self.winfo_toplevel()
		top.rowconfigure(0, weight=1)
		top.columnconfigure(0, weight=1)
		top.config(borderwidth=10)
		
		self.rowconfigure(3, weight=1)
		self.columnconfigure(0, weight=1)
		self.columnconfigure(1, weight=2)
		self.columnconfigure(2, weight=1)
		self.columnconfigure(3, weight=1)
		
		self.user_info = tk.Label(self)
		self.user_info_var = tk.StringVar()
		self.user_info["textvariable"] = self.user_info_var
		self.user_info_var.set("@"+self.conn.user_data["user"]["username"])
		self.user_info.grid(column=0, row=1, columnspan=4)
		
		self.join_lbl = tk.Label(self, text="Join a Chat")
		self.join_lbl.grid(column=0, row=1)
		
		self.join = tk.Entry(self)
		self.join_var = tk.StringVar()
		self.join["textvariable"] = self.join_var
		self.join.bind("<Key-Return>", self.join_room)
		self.join.grid(column=0, row=2)
		
		self.channel_list = tk.Listbox(self)
		self.channel_list.grid(column=0, row=3, sticky=tk.N+tk.S)
		self.channel_list.configure(exportselection=False)
		
		self.leave = tk.Button(self, text="Leave", command=self.leave_room)
		self.leave.grid(column=0, row=4, sticky=tk.E+tk.W)
		
		self.message_area = tk.Text(self, wrap='word', height=28, width=80)
		self.message_area.grid(column=1, row=3, columnspan=2, sticky=tk.N+tk.S+tk.E+tk.W)
		self.message_area.tag_configure('normal', font=('Courier', 10,))
		self.message_area.tag_configure('italics', font=('Courier', 10, 'italic',))
		self.message_area.tag_configure('bold', font=('Courier', 10, 'bold',))
		self.message_area.tag_configure('bold-italics', font=('Courier', 10, 'bold italic',))
		self.message_area.tag_configure('admin-bold', font=('Courier', 10, 'bold',), foreground='red')
		self.message_area.tag_configure('admin-bold-italics', font=('Courier', 10, 'bold italic',), foreground='red')
		self.message_area.tag_configure('mod-bold', font=('Courier', 10, 'bold',), foreground='blue')
		self.message_area.tag_configure('mod-bold-italics', font=('Courier', 10, 'bold italic',), foreground='blue')
		self.message_area.tag_configure('op-bold', font=('Courier', 10, 'bold',), foreground='lime green')
		self.message_area.tag_configure('op-bold-italics', font=('Courier', 10, 'bold italic',), foreground='lime green')
		self.message_area.config(state=tk.DISABLED)
		
		self.join_lbl = tk.Label(self, text="Users")
		self.join_lbl.grid(column=3, row=1)
		
		self.user_list = tk.Listbox(self)
		self.user_list.grid(column=3, row=3, sticky=tk.N+tk.S)
		self.user_list.configure(exportselection=False)
		
		self.message = tk.Entry(self)
		self.message_var = tk.StringVar()
		self.message["textvariable"] = self.message_var
		self.message.bind("<Key-Return>", self.send_message)
		self.message.grid(column=1, row=4, sticky=tk.N+tk.S+tk.E+tk.W)
		
		self.send = tk.Button(self, text="Send", command=self.send_message)
		self.send.grid(column=2, row=4, sticky=tk.E+tk.W)
		
		self.mention = tk.Button(self, text="Mention", command=self.mention_user)
		self.mention.grid(column=3, row=4, sticky=tk.E+tk.W)
		
		self.after(0, self.poll)
	def poll(self):
		if self.channel_list.size() == 0:
			self.active_channel = ""
			self.message_area.config(state=tk.NORMAL)
			self.message_area.delete('1.0', tk.END)
			self.message_area.config(state=tk.DISABLED)
			self.user_list.delete(0, tk.END)
			self.refresh_lists()
		else:
			sel = self.get_channel_from_list_name(self.channel_list.get(tk.ACTIVE))
			if sel != self.active_channel:
				self.active_channel = sel
				if len(sel) and not self.rooms[sel]["loaded"]:
					self.conn.join(sel)
				else:
					self.refresh_lists()
		if self.focus_displayof() is not None and (self.new_msg_count > 0 or self.new_pm):
			self.new_msg_count = 0
			self.new_pm = False
			self.update_title()
		self.after(250, self.poll)
	def mention_user(self):
		if self.user_list.size() == 0: return
		self.message.insert(tk.INSERT, "@{} ".format(
			re.sub("^\\[\\w+\\]\\s+", "", self.user_list.get(tk.ACTIVE))
		))
		self.message.focus_set()
	def join_room(self, event):
		r = self.conn.get_normalized_channel_name(self.join_var.get())
		if r is None or r in self.rooms: return
		self.conn.join(r)
	def leave_room(self):
		if len(self.active_channel):
			self.conn.leave(self.active_channel)
	def send_message(self, event=None):
		sel = self.active_channel
		msg = self.message_var.get().strip()[:255]
		self.message_var.set("")
		if len(sel) and len(msg):
			r = self.channel_list.get(tk.ACTIVE)
			self.conn.message(r, msg)
			time = datetime.now()
			time = ("00"+str(time.hour))[-2:] + ":" + ("00"+str(time.minute))[-2:]
			self.rooms[r]["messages"].append({
				"created_at": time,
				"sender": {"id": self.conn.user_data["user"]["id"],
					"username": self.conn.user_data["user"]["username"]},
				"body": msg
			})
			if len(self.rooms[r]["messages"]) > 100:
				self.refresh_messages(True)
			else:
				self.refresh_messages()
	def before_close(self):
		for r in self.rooms:
			self.conn.leave(r)
		self.conn.wait_for_logout()
		self.master.destroy()
	def on_message(self, conn, data):
		try:
			if data["event"] == "subscribed":
				name = self.conn.get_channel_name(data["channel"])
				uid = self.conn.get_user_id(name)
				messages = self.conn.get_messages(name)
				if messages is not None and "data" in messages:
					messages = messages["data"]
				else:
					messages = []
				messages.reverse()
				if name in self.rooms:
					self.rooms[name]["messages"] = messages
					self.rooms[name]["loaded"] = True
					idx = -1
					for i in range(self.channel_list.size()):
						if self.channel_list.get(i) == self.rooms[name]["list_name"]:
							idx = i
							break
					if idx < 0: return
					self.rooms[name]["list_name"] = name
					self.channel_list.delete(idx)
					self.channel_list.insert(idx, name)
					self.channel_list.selection_clear(0, tk.END)
					self.channel_list.selection_set(idx)
					self.channel_list.activate(idx)
					self.refresh_lists()
				else:
					self.join_var.set("")
					self.channel_list.insert(tk.END, name)
					self.channel_list.selection_clear(0, tk.END)
					self.channel_list.selection_set(tk.END)
					self.channel_list.activate(self.channel_list.size()-1)
					self.rooms[name] = {"channel_name":data["channel"], "id":uid,
						"messages":messages, "members":data["members"],
						"list_name":name, "loaded":True}
			elif data["event"] == "unsubscribed":
				f = None
				for k in self.rooms:
					if self.rooms[k]["channel_name"] == data["channel"]:
						f = k
						break
				if f is None: return
				for i in range(self.channel_list.size()):
					if self.get_channel_from_list_name(self.channel_list.get(i)) == k:
						self.channel_list.delete(i)
						break
				del self.rooms[k]
				if self.channel_list.size() > 0:
					self.channel_list.selection_clear(0, tk.END)
					self.channel_list.selection_set(0)
			elif data["event"] == "client-message":
				channel = None
				for c in self.rooms:
					if self.rooms[c]["channel_name"] == data["channel"]:
						channel = c
						break
				if channel is None: return
				self.new_msg_count += 1
				self.update_title()
				data = data["data"].copy()
				time = datetime.now()
				data["created_at"] = ("00"+str(time.hour))[-2:] + ":" + ("00"+str(time.minute))[-2:]
				self.rooms[channel]["messages"].append(data)
				if len(self.rooms[channel]["messages"]) > 100:
					if channel == self.active_channel:
						self.refresh_messages(True)
					else:
						self.rooms[channel]["messages"] = self.rooms[channel]["messages"][-100:]
				elif channel == self.active_channel:
					self.refresh_messages(True)
			elif data["event"] == 10: # This is a PM
				id1, id2 = int(data["source_id"]), int(data["user_id"])
				if id2 < id1:
					id1, id2 = id2, id1
				name = "@" + data["source"]["username"]
				uid = self.conn.get_user_id(data["source"]["username"])
				self.channel_list.insert(tk.END, name + " *")
				self.rooms[name] = {"channel_name":"prv_{}_{}".format(id1,id2), "id":uid,
					"messages":[], "members":[], "list_name":name+" *", "loaded":False}
				self.new_pm = True
				self.update_title()
			elif data["event"] == "member-added":
				channel = self.conn.get_channel_name(data["channel"])
				self.rooms[channel]["members"].append(data["data"])
				if channel == self.active_channel:
					self.refresh_members()
			elif data["event"] == "member-removed":
				channel = self.conn.get_channel_name(data["channel"])
				u = None
				for m in self.rooms[channel]["members"]:
					if int(m["id"]) == int(data["data"]["id"]):
						u = m
						break
				if u is None: return
				self.rooms[channel]["members"].remove(u)
				if channel == self.active_channel:
					self.refresh_members()
			else:
				print(data)
		except Exception:
			traceback.print_exc()
	def update_title(self):
		if self.focus_displayof() is None:
			pm = "* " if self.new_pm else ""
			if self.new_msg_count > 0:
				self.master.title("{}FinitPy ({})".format(pm, self.new_msg_count))
			else:
				self.master.title("{}FinitPy".format(pm))
		else:
			self.master.title("FinitPy")
	def refresh_lists(self):
		if len(self.active_channel) > 0:
			self.user_info_var.set("@"+self.conn.user_data["user"]["username"]+" - "+self.active_channel)
		else:
			self.user_info_var.set("@"+self.conn.user_data["user"]["username"])
		self.refresh_members()
		self.refresh_messages()
	def get_channel_from_list_name(self, lname):
		if len(lname) == 0: return ""
		for c in self.rooms:
			if self.rooms[c]["list_name"] == lname:
				return c
		return ""
	def refresh_members(self):
		r = self.active_channel
		if len(r) == 0: return
		self.rooms[r]["members"].sort(key=lambda u:(
			int(u["id"])!=1,
			not (True in [r.upper() == self.conn.get_channel_name(s).upper() for s in u["mod_powers"]]),
			u["username"].upper()
		))
		prev_active_user = self.user_list.get(tk.ACTIVE)
		active_index = -1
		self.user_list.delete(0, tk.END)
		prev_name = ""
		for i,u in enumerate(self.rooms[r]["members"]):
			username = u["username"]
			if int(u["id"]) == 1:
				username = "[ADMIN] " + username
			else:
				for m in u["mod_powers"]:
					if self.conn.get_channel_name(m).upper() == r.upper():
						username = "[MOD] " + username
						break
			if prev_name != username:
				self.user_list.insert(tk.END, username)
			if username == prev_active_user:
				active_index = i
			prev_name = username
		if active_index >= 0:
			self.user_list.activate(active_index)
	def _add_message(self, m):
		if len(m["created_at"]) <= 5:
			d = m["created_at"]
		else:
			d = utc2local(datetime.strptime(m["created_at"], "%Y-%m-%d %H:%M:%S"))
			d = ("00"+str(d.hour))[-2:] + ":" + ("00"+str(d.minute))[-2:]
		user_type = ""
		if m["sender"]["id"] == 1:
			user_type = "admin-"
		elif m["sender"]["username"] == self.conn.user_data["user"]["username"]:
			user_type = "op-"
		else:
			for p in m["sender"]["mod_powers"]:
				if self.conn.get_channel_name(p).upper() == self.active_channel.upper():
					user_type = "mod-"
					break
		if re.match("^/me\s", m["body"], re.I):
			user_style = user_type + "bold-italics"
			self.message_area.insert(tk.END, "{} * ".format(d), "normal")
			self.message_area.insert(tk.END, "@"+m["sender"]["username"], user_style)
			self.message_area.insert(tk.END, m["body"][3:]+"\n", "italics")
		else:
			user_style = user_type + "bold"
			self.message_area.insert(tk.END, d+" ", "normal")
			self.message_area.insert(tk.END, "@"+m["sender"]["username"]+": ", user_style)
			self.message_area.insert(tk.END, m["body"]+"\n", "normal")
	def refresh_messages(self, refresh=False):
		r = self.active_channel
		if len(r) == 0: return
		if refresh == True:
			discarded = []
			if len(self.rooms[r]["messages"]) > 100:
				discarded = self.rooms[r]["messages"][:-100]
				self.rooms[r]["messages"] = self.rooms[r]["messages"][-100:]
			lines_to_remove = 0
			for d in discarded:
				lines_to_remove += 1 + len(list(filter(lambda x:x=='\n', d["body"])))
			self.message_area.config(state=tk.NORMAL)
			if lines_to_remove > 0:
				self.message_area.delete('1.0', str(lines_to_remove+1)+'.0')
			for i in range(100-len(discarded),100):
				self._add_message(self.rooms[r]["messages"][i])
			self.message_area.see(tk.END)
			self.message_area.config(state=tk.DISABLED)
		else:
			self.message_area.config(state=tk.NORMAL)
			self.message_area.delete('1.0', tk.END)
			for m in self.rooms[r]["messages"]:
				self._add_message(m)
			self.message_area.see(tk.END)
			self.message_area.config(state=tk.DISABLED)

class FinitApp:
	def __init__(self):
		self.client = FinitClient()
		self.root = tk.Tk()
		self.root.title("FinitPy - Sign in")
		self.app = FinitPyLogin(master=self.root, on_login=self.on_login)
		self.app.mainloop()
	def on_login(self, email, pwd):
		if self.client.login(email, pwd):
			self.root.destroy()
			self.root = tk.Tk()
			self.root.title("FinitPy")
			self.app = FiniyPyMain(master=self.root, conn=self.client)
			self.app.mainloop()
		else:
			self.app.set_error("Wrong credentials")

if __name__ == "__main__":
	FinitApp()
