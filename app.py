# app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
from bsp_data import (
    PATH_ALWAYS_INCLUDE,
    PATH_GLOBAL_ENUMS,
    PATH_MASTER_LUA,
    PATH_MASTER_MISSION_TREE,
)
from bsp_parser import BSPParser

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("BSP Mission Loader Tool")
        self.root.geometry("700x500")
        
        self.parser = None
        self.game_dir = tk.StringVar()
        self.all_missions = [] # Store all for filtering

        # --- Directory Selection ---
        tk.Label(root, text="Battlestations Pacific Directory:", font=('bold')).pack(pady=(10, 5))
        
        dir_frame = tk.Frame(root)
        dir_frame.pack(fill="x", padx=10)
        
        self.entry_dir = tk.Entry(dir_frame, textvariable=self.game_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True)
        tk.Button(dir_frame, text="Browse", command=self.select_directory).pack(side="right", padx=5)

        tk.Button(root, text="Load Game Data", command=self.load_data, bg="#dddddd").pack(pady=10)

        # --- Filter Section ---
        filter_frame = tk.Frame(root)
        filter_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(filter_frame, text="Filter by Group:").pack(side="left")
        
        self.group_combo = ttk.Combobox(filter_frame, state="readonly")
        self.group_combo.pack(side="left", padx=5)
        self.group_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        # --- Mission List ---
        self.tree = ttk.Treeview(root, columns=("ID", "Name", "Group"), show='headings', selectmode="extended")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Mission Name")
        self.tree.heading("Group", text="Campaign/Group")
        
        self.tree.column("ID", width=80)
        self.tree.column("Name", width=300)
        self.tree.column("Group", width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0))
        scrollbar.pack(side="right", fill="y", padx=(0, 10))

        # --- Action ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(btn_frame, text="GENERATE LOADER", command=self.generate, bg="#aaffaa", height=2).pack(fill="x")
        
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Waiting for game directory...")
        tk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken").pack(fill="x", padx=10, pady=5)

    def select_directory(self):
        d = filedialog.askdirectory()
        if d:
            self.game_dir.set(d)

    def load_data(self):
        gd = self.game_dir.get()
        if not gd or not os.path.exists(gd):
            messagebox.showerror("Error", "Please select a valid game directory.")
            return

        if not os.path.exists(os.path.join(gd, PATH_MASTER_LUA)):
            messagebox.showerror("Error", "Could not find 'scripts/datatables/autoload/Master_vehicleclasses.lua'.\nCheck the directory.")
            return

        master_tree_path = os.path.join(gd, PATH_MASTER_MISSION_TREE)
        if not os.path.exists(master_tree_path):
            messagebox.showerror("Error", "Could not find 'scripts/datatables/master_missiontree.lua'.\nCheck the directory.")
            return

        self.status_var.set("Status: Parsing files... please wait.")
        self.root.update()

        self.parser = BSPParser(gd)
        
        # Load AlwaysInclude file (optional, won't fail if missing)
        res = self.parser.load_always_include(os.path.join(gd, PATH_ALWAYS_INCLUDE))
        if "Error" in res:
            messagebox.showwarning("Warning", f"Could not load AlwaysInclude file:\n{res}\n\nContinuing without it...")
        
        # Load Enums
        res = self.parser.load_global_enums(os.path.join(gd, PATH_GLOBAL_ENUMS))
        if "Error" in res:
            messagebox.showerror("Error", res)
            return
        
        path_unitlib = os.path.join(gd, "scripts", "datatables", "master_unitlib.lua")
        
        # Load Master Classes
        res = self.parser.load_master_vehicle_classes(os.path.join(gd, PATH_MASTER_LUA))
        if "Error" in res:
            messagebox.showerror("Error", res)
            return

        self.status_var.set("Status: Loading UnitLib...")
        self.root.update()

        res = self.parser.load_master_unitlib(path_unitlib)
        if "Error" in res:
            print("UnitLib Load Warning:", res)

        # Load Missions
        res = self.parser.load_missions(master_tree_path)
        if "Error" in res:
            messagebox.showerror("Error", res)
            return

        self.all_missions = self.parser.missions
        
        # Setup Filter with proper grouping
        groups = sorted(list(set(m.group for m in self.all_missions)))
        groups.insert(0, "All Missions")
        self.group_combo['values'] = groups
        self.group_combo.current(0)

        self.apply_filter()
        
        # Count missions by type
        campaign_count = sum(1 for m in self.all_missions if m.group != "Multiplayer & Skirmish")
        mp_count = sum(1 for m in self.all_missions if m.group == "Multiplayer & Skirmish")
        
        self.status_var.set(f"Status: Loaded {len(self.all_missions)} missions ({campaign_count} campaign, {mp_count} multiplayer) and {len(self.parser.master_units)} units.")

    def apply_filter(self, event=None):
        selected_group = self.group_combo.get()
        
        self.tree.delete(*self.tree.get_children())
        
        for m in self.all_missions:
            if selected_group == "All Missions" or m.group == selected_group:
                self.tree.insert("", "end", values=(m.id, m.name, m.group))

    def generate(self):
        if not self.parser:
            messagebox.showwarning("Warning", "Please load game data first.")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one mission from the list.")
            return

        missions = []
        for item_id in selected:
            item = self.tree.item(item_id)
            mission_id = item['values'][0]
            mission = next((m for m in self.all_missions if m.id == str(mission_id)), None)
            if mission:
                missions.append(mission)

        if not missions:
            messagebox.showwarning("Warning", "No valid missions selected.")
            return

        if len(missions) > 1:
            proceed = messagebox.askyesno(
                "Unstable Combination",
                "Loading multiple missions at once can be unstable. Continue anyway?",
            )
            if not proceed:
                return

        res = self.parser.generate_for_missions(missions)
        if "Error" in res:
            messagebox.showerror("Failed", res)
        else:
            messagebox.showinfo("Success", res)
            self.status_var.set(f"Status: Generated loader for {', '.join(m.name for m in missions)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
