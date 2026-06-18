import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

# ==========================================
# FastAPI Initialization & Configuration
# ==========================================
app = FastAPI(
    title="D Industries Server Base",
    description="Operational command, automated server-pinging, and high-performance in-memory database system.",
    version="3.4.0"
)

# Enable CORS for full flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# Database Modeling & Storage
# ==========================================
class DBRecord(BaseModel):
    id: str = Field(..., description="Unique alphanumeric identifier for the asset")
    name: str = Field(..., description="Name or designation of the tactical asset")
    category: str = Field(..., description="Classification category (e.g., mainframe, security, node)")
    status: str = Field("ONLINE", description="Current operating status (ONLINE, OFFLINE, MAINTENANCE, OVERLOAD)")
    security_clearance: int = Field(1, ge=1, le=5, description="Required clearance level (1-5)")
    payload: dict = Field(default_factory=dict, description="Additional custom metadata fields")
    last_synchronized: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

# In-Memory Database (Pre-seeded with mock tactical data)
IN_MEMORY_DB: Dict[str, DBRecord] = {
    "D-M-01": DBRecord(
        id="D-M-01",
        name="Mainframe Alpha",
        category="Computation Core",
        status="ONLINE",
        security_clearance=5,
        payload={"load": "42%", "temp": "38C", "region": "Sublevel-3"},
        last_synchronized=datetime.utcnow().isoformat() + "Z"
    ),
    "D-S-09": DBRecord(
        id="D-S-09",
        name="Aegis Firewalls",
        category="Cyber Security",
        status="ONLINE",
        security_clearance=4,
        payload={"threat_level": "LOW", "active_intercepts": 12},
        last_synchronized=datetime.utcnow().isoformat() + "Z"
    ),
    "D-Q-55": DBRecord(
        id="D-Q-55",
        name="Quantum Router Node",
        category="Quantum Comm-Link",
        status="MAINTENANCE",
        security_clearance=3,
        payload={"entanglement_rate": "99.8%", "active_tunnels": 4},
        last_synchronized=datetime.utcnow().isoformat() + "Z"
    )
}

# Simulated Servers list for the "Pinger" service
MONITORED_SERVERS = [
    {"id": "srv-alpha", "name": "Mainframe Alpha", "ip": "10.100.1.5", "type": "Core"},
    {"id": "srv-beta", "name": "Aegis Firewalls", "ip": "10.100.1.12", "type": "Security"},
    {"id": "srv-gamma", "name": "Quantum Router Node", "ip": "10.100.2.55", "type": "Network"},
    {"id": "srv-delta", "name": "D-Ind Storage Array", "ip": "10.100.4.10", "type": "Database"},
    {"id": "srv-epsilon", "name": "Auxiliary Power grid", "ip": "10.100.5.2", "type": "Infrastructure"}
]

# Simple in-memory logs for DB actions
db_logs: List[dict] = []

def add_log(action: str, target: str, status: str = "SUCCESS"):
    db_logs.append({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "target": target,
        "status": status
    })
    if len(db_logs) > 50:
        db_logs.pop(0)

# ==========================================
# REST API Endpoints (CRUD + Control)
# ==========================================

@app.get("/api/db", response_model=List[DBRecord])
def get_all_records():
    """Retrieve all assets currently stored in the D Industries Server Base."""
    return list(IN_MEMORY_DB.values())

@app.get("/api/db/{record_id}", response_model=DBRecord)
def get_record(record_id: str):
    """Retrieve a specific database record by its unique ID."""
    if record_id not in IN_MEMORY_DB:
        add_log("READ_ERROR", f"Record {record_id} not found", "FAILED")
        raise HTTPException(status_code=404, detail="Record not found in Server Base Database.")
    return IN_MEMORY_DB[record_id]

@app.post("/api/db", status_code=status.HTTP_201_CREATED, response_model=DBRecord)
def create_record(record: DBRecord):
    """Insert or overwrite an operational asset record in the database."""
    record.last_synchronized = datetime.utcnow().isoformat() + "Z"
    IN_MEMORY_DB[record.id] = record
    add_log("CREATE/UPDATE", f"Record {record.id} ({record.name})")
    return record

@app.delete("/api/db/{record_id}")
def delete_record(record_id: str):
    """Securely purge an asset record from the server base database."""
    if record_id not in IN_MEMORY_DB:
        add_log("DELETE_ERROR", f"Failed deletion for {record_id}", "FAILED")
        raise HTTPException(status_code=404, detail="Record not found.")
    deleted = IN_MEMORY_DB.pop(record_id)
    add_log("PURGE", f"Record {record_id} purged from system")
    return {"message": f"Asset {record_id} ({deleted.name}) successfully purged."}

@app.get("/api/sys/logs")
def get_database_logs():
    """Returns database operation logs."""
    return db_logs[-15:]

# ==========================================
# Real-Time Server Pinger & SSE Stream
# ==========================================
async def server_pinger_generator():
    """
    Simulates automated asynchronous ping operations on servers and databases.
    Streams structured metrics down to the HTML dashboard using Server-Sent Events (SSE).
    """
    ping_count = 0
    while True:
        ping_count += 1
        
        # Ping a random subset of our monitored servers
        ping_results = []
        for server in MONITORED_SERVERS:
            # Generate simulated metrics
            latency = round(random.uniform(2.5, 45.0), 2)
            is_alive = random.choices([True, False], weights=[94, 6])[0] # 94% uptime simulation
            packet_loss = 0.0 if is_alive else 100.0
            
            # Fluctuate the latency for visual excitement
            if is_alive and latency > 35.0:
                status_text = "CONGESTED"
            elif is_alive:
                status_text = "STABLE"
            else:
                status_text = "OFFLINE"
                latency = 0.0

            ping_results.append({
                "id": server["id"],
                "name": server["name"],
                "ip": server["ip"],
                "type": server["type"],
                "latency_ms": latency,
                "packet_loss": packet_loss,
                "status": status_text
            })

        # Base System Vitals
        vitals = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_utilization": round(random.uniform(15.4, 68.2), 1),
            "memory_usage": round(random.uniform(40.1, 45.9), 1),
            "db_size_records": len(IN_MEMORY_DB),
            "pings_executed": ping_count,
            "servers": ping_results,
            "recent_logs": db_logs[-5:] # Attach recent logs directly to UI stream
        }

        # Format as standard Server-Sent Event (SSE) text stream
        yield f"event: server-ping-pulse\ndata: {json.dumps(vitals)}\n\n"
        
        # Auto ping interval (e.g., every 2 seconds)
        await asyncio.sleep(2)

@app.get("/api/stream")
def stream_operational_data():
    """
    Establish a high-frequency real-time event pipeline streaming database state, 
    and diagnostic server pings directly to clients.
    """
    return StreamingResponse(server_pinger_generator(), media_type="text/event-stream")

# ==========================================
# Interactive HTML Frontend Dashboard
# ==========================================
@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Generates and serves the complete premium responsive visual command suite."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>D Industries Server Base - DB Command & Pinger</title>
        <!-- Tailwind CSS CDN -->
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- Lucide Icons (Inline SVGs supported, also using raw SVG fallback for speed) -->
        <script src="https://unpkg.com/lucide@latest"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Rajdhani:wght@500;600;700&display=swap');
            
            body {
                font-family: 'Rajdhani', sans-serif;
                background-color: #0b0f19;
                color: #e2e8f0;
            }
            .monospace {
                font-family: 'Fira Code', monospace;
            }
            /* Custom glowing animations for terminal aesthetic */
            .glow-blue {
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.45);
            }
            .glow-amber {
                box-shadow: 0 0 15px rgba(245, 158, 11, 0.45);
            }
            .cyber-border {
                border: 1px solid rgba(59, 130, 246, 0.2);
            }
            .cyber-border:hover {
                border-color: rgba(59, 130, 246, 0.6);
                box-shadow: 0 0 10px rgba(59, 130, 246, 0.15);
            }
        </style>
    </head>
    <body class="min-h-screen flex flex-col justify-between selection:bg-blue-600 selection:text-white">

        <!-- Top Header Panel -->
        <header class="border-b border-blue-900/50 bg-slate-950/80 backdrop-blur px-6 py-4 sticky top-0 z-50">
            <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-10 w-10 rounded bg-blue-600 flex items-center justify-center font-bold text-xl text-white tracking-widest border border-blue-400 shadow-lg shadow-blue-500/20">
                        DI
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-300">
                            D INDUSTRIES SERVER BASE
                        </h1>
                        <p class="text-xs text-blue-400 monospace uppercase tracking-widest">
                            Autonomous DB System // Real-Time Network Pinger
                        </p>
                    </div>
                </div>
                
                <!-- Status Indicators -->
                <div class="flex items-center gap-6 text-sm monospace">
                    <div class="flex items-center gap-2">
                        <span class="relative flex h-3.5 w-3.5">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500"></span>
                        </span>
                        <span>API ONLINE</span>
                    </div>
                    <div class="flex items-center gap-2 bg-blue-950/40 px-3 py-1.5 rounded border border-blue-800/40">
                        <span class="text-blue-400 font-bold">SSE PING RATE:</span>
                        <span class="text-emerald-400" id="pulse-rate">2.0s</span>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Body Command Grid -->
        <main class="max-w-7xl mx-auto px-4 py-6 w-full flex-grow grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            <!-- Left Panel: Live Automated Ping Vitals (5 cols) -->
            <section class="lg:col-span-5 flex flex-col gap-6">
                <!-- Vitals Summary Card -->
                <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800 backdrop-blur flex flex-col gap-4">
                    <h2 class="text-lg font-bold tracking-wide text-blue-300 flex items-center gap-2 border-b border-slate-800 pb-2">
                        <i data-lucide="cpu" class="w-5 h-5 text-blue-400"></i> SYSTEM DIAGNOSTICS & PINGS
                    </h2>
                    
                    <div class="grid grid-cols-3 gap-3">
                        <div class="bg-slate-950/80 p-3 rounded border border-slate-800 text-center">
                            <p class="text-xs text-slate-400 uppercase">CPU Vitals</p>
                            <p class="text-xl font-bold text-blue-400 monospace mt-1" id="vital-cpu">--%</p>
                        </div>
                        <div class="bg-slate-950/80 p-3 rounded border border-slate-800 text-center">
                            <p class="text-xs text-slate-400 uppercase">Memory Allocation</p>
                            <p class="text-xl font-bold text-purple-400 monospace mt-1" id="vital-mem">--%</p>
                        </div>
                        <div class="bg-slate-950/80 p-3 rounded border border-slate-800 text-center">
                            <p class="text-xs text-slate-400 uppercase">DB Core Rows</p>
                            <p class="text-xl font-bold text-amber-400 monospace mt-1" id="vital-db-size">--</p>
                        </div>
                    </div>
                    
                    <div class="text-xs text-slate-400 flex justify-between items-center bg-slate-950/50 p-2 rounded">
                        <span>Ping Pulse Count: <strong id="ping-count" class="text-white monospace">--</strong></span>
                        <span>Latest Update: <strong id="latest-ts" class="text-white monospace">--:--:--</strong></span>
                    </div>
                </div>

                <!-- Servers Grid and Auto-Pinger Status -->
                <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800 backdrop-blur flex-grow flex flex-col gap-4">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <h2 class="text-lg font-bold tracking-wide text-blue-300 flex items-center gap-2">
                            <i data-lucide="activity" class="w-5 h-5 text-emerald-400 animate-pulse"></i> LIVE SERVER RESPONSES
                        </h2>
                        <span class="text-xs uppercase bg-emerald-950 text-emerald-400 px-2.5 py-0.5 rounded-full font-semibold monospace animate-pulse">
                            Auto-Polling HTML
                        </span>
                    </div>
                    
                    <!-- Dynamic server lists -->
                    <div id="ping-targets-list" class="flex flex-col gap-3 overflow-y-auto max-h-[420px] pr-1">
                        <!-- Simulated server items populate dynamically via JS -->
                        <div class="text-center py-8 text-slate-500">
                            <p class="animate-pulse">Awaiting payload telemetry streams...</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Right Panel: Database Control Room (7 cols) -->
            <section class="lg:col-span-7 flex flex-col gap-6">
                <!-- Database Records List & Actions -->
                <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800 backdrop-blur flex flex-col gap-4">
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-800 pb-3">
                        <div>
                            <h2 class="text-xl font-bold tracking-wide text-amber-400 flex items-center gap-2">
                                <i data-lucide="database" class="w-5 h-5"></i> D-IND DATABASE ENGINE
                            </h2>
                            <p class="text-xs text-slate-400 monospace">CRUD Operations directed to FastAPI /api/db</p>
                        </div>
                        <button onclick="openCreateModal()" class="w-full sm:w-auto bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-slate-950 font-bold px-4 py-2 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/10">
                            <i data-lucide="plus-circle" class="w-4 h-4"></i> Create DB Record
                        </button>
                    </div>

                    <!-- Database Cards Container -->
                    <div id="db-records-container" class="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[380px] overflow-y-auto pr-1">
                        <!-- Dynamic content filled by API fetching -->
                        <div class="col-span-full text-center py-12 text-slate-500">
                            <p class="animate-pulse">Contacting database engine...</p>
                        </div>
                    </div>
                </div>

                <!-- Database Operational Log Terminal -->
                <div class="bg-slate-950/80 rounded-xl p-5 border border-slate-900 flex-grow flex flex-col gap-3">
                    <h3 class="text-sm font-bold tracking-wider text-slate-400 monospace flex items-center gap-2 border-b border-slate-900 pb-2">
                        <i data-lucide="terminal" class="w-4 h-4 text-amber-500"></i> TRANSACTION METADATA LOGS
                    </h3>
                    <div id="terminal-logs" class="monospace text-xs text-blue-300 h-44 overflow-y-auto flex flex-col gap-1 pr-1 bg-black/40 p-3 rounded border border-slate-900/80">
                        <!-- Log messages go here -->
                        <span class="text-slate-500">// Transaction logs initializing...</span>
                    </div>
                </div>
            </section>
        </main>

        <!-- Footer -->
        <footer class="border-t border-slate-900 bg-slate-950 py-3 px-6 text-center text-xs text-slate-500">
            <p>&copy; 2026 D Industries. Unauthorized access is highly trace-routed. Developed on FastAPI framework.</p>
        </footer>

        <!-- Modal for Creating/Editing DB Records -->
        <div id="db-modal" class="hidden fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="bg-slate-900 rounded-xl max-w-lg w-full border border-amber-500/40 shadow-2xl glow-amber overflow-hidden flex flex-col">
                <div class="bg-amber-500/10 border-b border-amber-500/20 px-6 py-4 flex justify-between items-center">
                    <h3 class="text-xl font-bold tracking-wide text-amber-400 flex items-center gap-2">
                        <i data-lucide="database-backup" class="w-5 h-5"></i> DB Operation Console
                    </h3>
                    <button onclick="closeModal()" class="text-slate-400 hover:text-white transition-colors">
                        <i data-lucide="x" class="w-6 h-6"></i>
                    </button>
                </div>
                <form id="db-form" onsubmit="handleFormSubmit(event)" class="p-6 flex flex-col gap-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div class="flex flex-col gap-1">
                            <label class="text-xs text-slate-400 uppercase tracking-wider">Asset ID</label>
                            <input required type="text" id="form-id" placeholder="e.g. D-S-10" class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-sm monospace">
                        </div>
                        <div class="flex flex-col gap-1">
                            <label class="text-xs text-slate-400 uppercase tracking-wider">Asset Name</label>
                            <input required type="text" id="form-name" placeholder="Aegis Subsystem" class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-sm">
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="flex flex-col gap-1">
                            <label class="text-xs text-slate-400 uppercase tracking-wider">Category</label>
                            <input required type="text" id="form-category" placeholder="Security Core" class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-sm">
                        </div>
                        <div class="flex flex-col gap-1">
                            <label class="text-xs text-slate-400 uppercase tracking-wider">Clearance (1-5)</label>
                            <input required type="number" id="form-clearance" min="1" max="5" value="1" class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-sm monospace">
                        </div>
                    </div>

                    <div class="flex flex-col gap-1">
                        <label class="text-xs text-slate-400 uppercase tracking-wider">Status</label>
                        <select id="form-status" class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-sm">
                            <option value="ONLINE">ONLINE</option>
                            <option value="OFFLINE">OFFLINE</option>
                            <option value="MAINTENANCE">MAINTENANCE</option>
                            <option value="OVERLOAD">OVERLOAD</option>
                        </select>
                    </div>

                    <div class="flex flex-col gap-1">
                        <label class="text-xs text-slate-400 uppercase tracking-wider">Payload Metadata (JSON Format)</label>
                        <textarea id="form-payload" rows="3" placeholder='{"load": "12%", "status": "nominal"}' class="bg-slate-950 text-white rounded border border-slate-800 focus:border-amber-500 focus:outline-none p-2 text-xs monospace"></textarea>
                    </div>

                    <div class="flex justify-end gap-3 mt-4">
                        <button type="button" onclick="closeModal()" class="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded font-semibold text-sm transition-colors">
                            Cancel
                        </button>
                        <button type="submit" class="bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-slate-950 px-5 py-2 rounded font-bold text-sm transition-colors">
                            Execute Record Commit
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Custom Notification Alert Box -->
        <div id="toast-notif" class="fixed bottom-6 right-6 z-50 bg-slate-900 border border-blue-500 text-white rounded-lg px-4 py-3 shadow-2xl transition-transform duration-300 transform translate-y-24 glow-blue flex items-center gap-3">
            <span id="toast-icon-wrapper" class="p-1 rounded-full bg-blue-500/20 text-blue-400">
                <i data-lucide="info" class="w-5 h-5"></i>
            </span>
            <div>
                <p id="toast-title" class="font-bold text-sm text-blue-300">SYSTEM NOTE</p>
                <p id="toast-msg" class="text-xs text-slate-300">Notification payload data.</p>
            </div>
        </div>

        <script>
            // Initialize lucide icons
            lucide.createIcons();

            // Dynamic Database Records
            async function fetchDbRecords() {
                try {
                    const response = await fetch('/api/db');
                    const records = await response.json();
                    renderDbRecords(records);
                } catch (err) {
                    console.error("Database connection failed", err);
                    showToast("DATABASE ERROR", "Failed to communicate with DB engine.", "error");
                }
            }

            function renderDbRecords(records) {
                const container = document.getElementById('db-records-container');
                container.innerHTML = '';

                if (records.length === 0) {
                    container.innerHTML = `
                        <div class="col-span-full text-center py-12 text-slate-500 border border-dashed border-slate-800 rounded-lg">
                            <p>Database is empty. Operational logs cleared.</p>
                        </div>
                    `;
                    return;
                }

                records.forEach(rec => {
                    const statusColorMap = {
                        "ONLINE": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                        "OFFLINE": "bg-rose-500/10 text-rose-400 border-rose-500/20",
                        "MAINTENANCE": "bg-amber-500/10 text-amber-400 border-amber-500/20",
                        "OVERLOAD": "bg-purple-500/10 text-purple-400 border-purple-500/20"
                    };
                    const statusClass = statusColorMap[rec.status] || "bg-slate-500/10 text-slate-400";

                    const card = document.createElement('div');
                    card.className = "bg-slate-950/80 rounded-lg p-4 border border-slate-800/80 hover:border-slate-700/80 transition-all flex flex-col justify-between gap-3 relative";
                    card.innerHTML = `
                        <div>
                            <div class="flex justify-between items-start gap-2">
                                <div>
                                    <span class="text-xs text-amber-500 font-bold monospace">${rec.id}</span>
                                    <h4 class="font-bold text-base text-slate-100 tracking-wide">${rec.name}</h4>
                                </div>
                                <span class="text-[10px] monospace uppercase tracking-wider px-2 py-0.5 border rounded ${statusClass}">
                                    ${rec.status}
                                </span>
                            </div>
                            <div class="mt-2 text-xs text-slate-400 flex flex-col gap-1 border-t border-slate-900 pt-2">
                                <p><span class="text-slate-600">Category:</span> ${rec.category}</p>
                                <p><span class="text-slate-600">Clearance Required:</span> Lvl ${rec.security_clearance}</p>
                                <div class="bg-black/30 p-2 rounded text-[11px] monospace text-slate-400 mt-1 max-h-20 overflow-y-auto">
                                    ${JSON.stringify(rec.payload)}
                                </div>
                            </div>
                        </div>
                        <div class="flex justify-between items-center border-t border-slate-900 pt-2 mt-1">
                            <span class="text-[10px] text-slate-500 monospace">sync: ${rec.last_synchronized.substring(11,19)}</span>
                            <div class="flex gap-2">
                                <button onclick='editRecord(${JSON.stringify(rec)})' class="p-1.5 hover:bg-slate-800 rounded text-blue-400 transition-all" title="Edit Record">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                                </button>
                                <button onclick="deleteRecord('${rec.id}')" class="p-1.5 hover:bg-slate-800 rounded text-rose-400 transition-all" title="Purge Record">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                </button>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            }

            // Real-Time Server-Sent Events Configuration
            function setupSseStream() {
                const sseSource = new EventSource('/api/stream');

                sseSource.addEventListener('server-ping-pulse', function(e) {
                    const data = JSON.parse(e.data);
                    
                    // Update Global Stats
                    document.getElementById('vital-cpu').innerText = `${data.cpu_utilization}%`;
                    document.getElementById('vital-mem').innerText = `${data.memory_usage}%`;
                    document.getElementById('vital-db-size').innerText = data.db_size_records;
                    document.getElementById('ping-count').innerText = data.pings_executed;
                    document.getElementById('latest-ts').innerText = data.timestamp.split(' ')[1];

                    // Render Automatic Servers Ping List
                    renderServerPings(data.servers);

                    // Update Logs Console
                    renderLogs(data.recent_logs);
                });

                sseSource.onerror = function() {
                    console.warn("SSE disconnected. Retrying stream protocol...");
                    showToast("CONNECTION DROPPED", "SSE pipeline interrupted, attempting to handshake...", "error");
                };
            }

            function renderServerPings(servers) {
                const list = document.getElementById('ping-targets-list');
                list.innerHTML = '';

                servers.forEach(srv => {
                    let statusColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
                    let glowEffect = "";
                    if (srv.status === "STABLE") {
                        statusColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
                    } else if (srv.status === "CONGESTED") {
                        statusColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                    }

                    const pingItem = document.createElement('div');
                    pingItem.className = `bg-slate-950/80 rounded-lg p-3 border border-slate-900 hover:border-slate-800 transition-all flex items-center justify-between gap-3 ${glowEffect}`;
                    
                    // Generate miniature simulated packet status grid
                    const packets = srv.status === "OFFLINE" 
                        ? `<span class="h-2 w-2 rounded-full bg-rose-500"></span><span class="h-2 w-2 rounded-full bg-rose-500"></span><span class="h-2 w-2 rounded-full bg-rose-500"></span>`
                        : `<span class="h-2 w-2 rounded-full bg-emerald-500"></span><span class="h-2 w-2 rounded-full bg-emerald-500"></span><span class="h-2 w-2 rounded-full bg-emerald-500"></span>`;

                    pingItem.innerHTML = `
                        <div class="flex items-center gap-3">
                            <div class="h-8 w-8 rounded bg-slate-900 border border-slate-800 flex items-center justify-center">
                                <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                            </div>
                            <div>
                                <h4 class="font-bold text-sm tracking-wide text-slate-200">${srv.name}</h4>
                                <p class="text-[10px] text-slate-500 monospace">${srv.ip} | ${srv.type}</p>
                            </div>
                        </div>

                        <div class="flex items-center gap-4 text-right">
                            <div>
                                <p class="text-xs font-bold text-slate-300 monospace">${srv.status === "OFFLINE" ? "LOST" : srv.latency_ms + " ms"}</p>
                                <p class="text-[9px] text-slate-500 uppercase font-semibold">Latency</p>
                            </div>
                            <div class="flex flex-col gap-0.5 items-center">
                                <span class="text-[9px] text-slate-500 monospace uppercase">Loss: ${srv.packet_loss}%</span>
                                <div class="flex gap-1">
                                    ${packets}
                                </div>
                            </div>
                        </div>
                    `;
                    list.appendChild(pingItem);
                });
            }

            function renderLogs(logs) {
                const logTerm = document.getElementById('terminal-logs');
                // Don't entirely clear unless full to maintain visual terminal history cascade
                let logsHTML = "";
                if (!logs || logs.length === 0) {
                    logTerm.innerHTML = `<span class="text-slate-600">// Idle listening...</span>`;
                    return;
                }
                logs.forEach(lg => {
                    const statusColor = lg.status === "FAILED" ? "text-rose-500" : "text-emerald-400";
                    logsHTML += `
                        <div>
                            <span class="text-slate-600">[${lg.timestamp}]</span> 
                            <span class="text-amber-400 font-semibold">${lg.action}</span> 
                            <span class="text-slate-400">${lg.target}</span> 
                            -> <span class="${statusColor} font-bold">[${lg.status}]</span>
                        </div>
                    `;
                });
                logTerm.innerHTML = logsHTML;
                // Auto scroll logs
                logTerm.scrollTop = logTerm.scrollHeight;
            }

            // DB Record Commits / Mutate Operations
            async function handleFormSubmit(event) {
                event.preventDefault();
                const id = document.getElementById('form-id').value.trim();
                const name = document.getElementById('form-name').value.trim();
                const category = document.getElementById('form-category').value.trim();
                const clearance = parseInt(document.getElementById('form-clearance').value);
                const status = document.getElementById('form-status').value;
                
                let payload = {};
                try {
                    const rawPayload = document.getElementById('form-payload').value.trim();
                    payload = rawPayload ? JSON.parse(rawPayload) : {};
                } catch(e) {
                    showToast("JSON ERROR", "Metadata is not a valid JSON structure.", "error");
                    return;
                }

                const record = {
                    id: id,
                    name: name,
                    category: category,
                    security_clearance: clearance,
                    status: status,
                    payload: payload
                };

                try {
                    const response = await fetch('/api/db', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(record)
                    });

                    if (response.ok) {
                        showToast("COMMIT COMPLETED", `Saved tactical asset "${id}" successfully.`, "success");
                        closeModal();
                        fetchDbRecords();
                    } else {
                        throw new Error("Failure creating record");
                    }
                } catch (err) {
                    showToast("API EXCEPTION", "Failed to commit record updates to DB.", "error");
                }
            }

            async function deleteRecord(recordId) {
                if(!confirm(`Authorize system directive to completely purge Asset ID: ${recordId}?`)) return;
                
                try {
                    const response = await fetch(`/api/db/${recordId}`, { method: 'DELETE' });
                    if (response.ok) {
                        showToast("PURGE SUCCESSFUL", `Asset ${recordId} was erased.`, "success");
                        fetchDbRecords();
                    } else {
                        showToast("PURGE ERROR", "Access denied or record does not exist.", "error");
                    }
                } catch (err) {
                    showToast("EXCEPTION OCCURRED", "Failed deleting asset registry item.", "error");
                }
            }

            // UI Actions
            function openCreateModal() {
                document.getElementById('form-id').disabled = false;
                document.getElementById('db-form').reset();
                document.getElementById('db-modal').classList.remove('hidden');
            }

            function editRecord(record) {
                document.getElementById('form-id').value = record.id;
                document.getElementById('form-id').disabled = true; // Key cannot be edited
                document.getElementById('form-name').value = record.name;
                document.getElementById('form-category').value = record.category;
                document.getElementById('form-clearance').value = record.security_clearance;
                document.getElementById('form-status').value = record.status;
                document.getElementById('form-payload').value = JSON.stringify(record.payload);
                document.getElementById('db-modal').classList.remove('hidden');
            }

            function closeModal() {
                document.getElementById('db-modal').classList.add('hidden');
            }

            function showToast(title, msg, type = "success") {
                const toast = document.getElementById('toast-notif');
                const titleEl = document.getElementById('toast-title');
                const msgEl = document.getElementById('toast-msg');
                const wrapper = document.getElementById('toast-icon-wrapper');

                titleEl.innerText = title;
                msgEl.innerText = msg;

                if (type === "success") {
                    toast.className = toast.className.replace(/border-rose-500|glow-rose/g, 'border-blue-500 glow-blue');
                    wrapper.className = "p-1 rounded-full bg-blue-500/20 text-blue-400";
                    wrapper.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
                } else {
                    toast.className = toast.className.replace(/border-blue-500|glow-blue/g, 'border-rose-500 glow-rose');
                    wrapper.className = "p-1 rounded-full bg-rose-500/20 text-rose-400";
                    wrapper.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
                }

                toast.classList.remove('translate-y-24');
                setTimeout(() => {
                    toast.classList.add('translate-y-24');
                }, 4000);
            }

            // Init Process
            window.onload = function() {
                fetchDbRecords();
                setupSseStream();
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# ==========================================
# Run Helper
# ==========================================
if __name__ == "__main__":
    import uvicorn
    # Pre-add initial log
    add_log("SYS_STARTUP", "D Industries Server Base core database operational")
    print("D Industries Server Base Online on http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
