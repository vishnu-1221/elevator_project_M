import sqlite3

# connect to DB (creates file automatically)
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

# create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS lift_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spare_part TEXT NOT NULL,
    description TEXT
)
""")


spare_parts = [
    "Accumulator 12V/7Ah", 
    "Shunt for door contact AZ01", 
    "Belt for door drive, L=2700mm", 
    "Toothed belt pulley Ø 130x61 Z49 (L&L)",
    "Printed circuit board LONIBVE 2.Q", 
    "Synchronisationsseil, PEGASUS DOOR", 
    "Electric door brake", 
    "Brake shoe lining", 
    "Buffer for door lock", 
    "Cable for door lock", 
    "Cable for drive with controller",
    "Encoder wires", 
    "Guiding brush pulley", 
    "W263, Brake disk 320x125x105mm", 
    "Magnet GSd 115.07-98, 180V, 40%ED, lifting height 2x3mm",
    "Neoprene 27BEC, seal with wire rope", 
    "Belt coated steel Megalinear 30 P 3.3, L=300m", 
    "Axial high-perf. fan HELIOS HRFW 200/4",
    "Brake FMB130-C FCRD112, 185Nm/150Nm", 
    "Seal set for cylinder LZA 120",
    "Door lock ZTV50F left", 
    "Kiekert, Motor GST50-12-084, 380V",
    "Contact for door lock",
    "Axle bearing assembly on the far left", 
    "Motor for folding door, 230V AC, 50Hz, single-phase",
    "Motor pulley D35", 
    "Door motor, asynchronous, three phases, 240/415V AC, 50Hz", 
    "Lower central bushing", 
    "Latch cam type V25 205V DC 100%ED",
    "Aritco, retiring cam STIN0006, old version with power supply", 
    "Shunt TK6 (> 6010623)", 
    "Oil collection container I7 H50 BFK 30", 
    "Lift buffer HPM - 40 x 430 max. 2,5 m/s", 
    "Buffer spacer Ø140x36mm, oval base plate 215x150mm",
    "Pizzato, position switch FR 701-K15V17", 
    "Inductive sensor SJ15-E, NO", 
    "Bernstein, SM-actuator, IN and I88 series, metall plunger",
    "Alarm push button station, d=40mm, 1NO, IP65", 
    "Oil-drip tank for rail 5 mm", 
    "Hydraulic Buffer V 16", 
    "Pressure spring FL-DR 2/1,25X8,4X21 N=6 STA2K", 
    "Door contact AZ02-1981",
    "Rope for over speed governor 6mm, length = 31 m", 
    "Remote tripping for Overspeedgovernor Gervall, 24VDC", 
    "Over speed governor HJ200SBU, right, Ts=0.32m/s", 
    "Seal kit for cylinder/jack 130 mm GMV",
    "Moris, seal set for piston dia 110 mm (3-MAP)",
    "Hydraulic block LRV175-1/175/251 complete",
    "Motor oil M200 Vanguard Gearing EP150",
    "Afriso, oil-water alarm unit ÖWU w/ wall rail oil-water probe",
    "Lever for hand pump LVR EHP10",
    "Brake modification kit AxienMOA115L/Dupar, 200V DC, 40%ED",
    "Brake magnet Sassi 30B0, 195+224V, for gear LEO/MF48/MF58/GEKO",
    "Conv. kit to dual-circuit brake for 11VT(R), 200V DC, 40%ED, long/short",
    ]

# clear old data (avoid duplicates)
cursor.execute("DELETE FROM lift_parts")

# insert spare parts
for part in spare_parts:
    cursor.execute(
        "INSERT INTO lift_parts (spare_part) VALUES (?)",
        (part,)
    )

conn.commit()

# fetch and print
cursor.execute("SELECT * FROM lift_parts")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()