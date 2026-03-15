"""
HWID Spoofer - Windows | Requires admin privileges.
Patches SMBiosData raw table + registry + WMI cache flush.
"""
import ctypes, winreg, random, uuid, sys, json, subprocess
from datetime import datetime

BIOS_PATH   = r'HARDWARE\DESCRIPTION\System\BIOS'
SMBIOS_PATH = r'SYSTEM\CurrentControlSet\services\mssmbios\Data'
CRIPTO_PATH = r'SOFTWARE\Microsoft\Cryptography'
WIN_NT_PATH = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
HW_PROF_PATH= r'SYSTEM\CurrentControlSet\Control\IDConfigDB\Hardware Profiles\0001'
NET_CLASS_PATH = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}'
BACKUP_FILE = 'hwid_backup.json'

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def rand_hex(n):
    return ''.join(random.choices('0123456789ABCDEF', k=n))

def _reg_get(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except: return None

def _reg_set(path, name, val, rtype=winreg.REG_SZ):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, rtype, val)
        return True
    except: return False

# ─── GETTERS (lit directement depuis SMBiosData) ──────────────────────────────

SMBIOS_HEADER = 8  # Windows SMBiosData a un header de 8 bytes avant les structures

def _read_smbios_raw():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SMBIOS_PATH) as k:
            raw, _ = winreg.QueryValueEx(k, 'SMBiosData')
            return bytes(raw)
    except: return None

def _smbios_get_string(data, struct_offset, str_index):
    """Retourne la string #str_index (1-based) d'une structure smBIOS."""
    if str_index == 0: return None
    length   = data[struct_offset + 1]
    i        = struct_offset + length
    current  = 1
    while i < len(data):
        # fin de zone strings = double null
        if data[i] == 0:
            break
        end = i
        while end < len(data) and data[end] != 0:
            end += 1
        s = data[i:end].decode('latin-1', errors='replace').strip()
        if current == str_index:
            return s if s else None
        current += 1
        i = end + 1
    return None

def _smbios_find(data, stype):
    """Trouve le premier offset d'une structure smBIOS par type. Skip le header Windows de 8 bytes."""
    offset = SMBIOS_HEADER
    while offset < len(data) - 4:
        t      = data[offset]
        length = data[offset + 1]
        if length < 4 or offset + length > len(data): break
        if t == stype: return offset
        i = offset + length
        while i < len(data) - 1:
            if data[i] == 0 and data[i+1] == 0: break
            i += 1
        offset = i + 2
        if t == 127: break
    return None

def get_cpu():
    # ProcessorId via WMI (registre kernel, fiable)
    try:
        out = subprocess.check_output('wmic cpu get ProcessorId /value',
            shell=True, stderr=subprocess.DEVNULL).decode(errors='ignore')
        for line in out.splitlines():
            if 'ProcessorId=' in line:
                v = line.split('=',1)[1].strip()
                if v: return v
    except: pass
    return 'N/A'

def get_bios():
    # Type 0: BIOSVersion = string à offset+5
    raw = _read_smbios_raw()
    if raw:
        off = _smbios_find(raw, 0)
        if off is not None and len(raw) > off + 5:
            s = _smbios_get_string(raw, off, raw[off + 5])
            if s: return s
    # fallback WMI
    try:
        out = subprocess.check_output('wmic bios get SerialNumber /value',
            shell=True, stderr=subprocess.DEVNULL).decode(errors='ignore')
        for line in out.splitlines():
            if 'SerialNumber=' in line:
                v = line.split('=',1)[1].strip()
                if v: return v
    except: pass
    return 'N/A'

def get_motherboard():
    # Type 2: SerialNumber = string à offset+7
    raw = _read_smbios_raw()
    if raw:
        off = _smbios_find(raw, 2)
        if off is not None and len(raw) > off + 7:
            s = _smbios_get_string(raw, off, raw[off + 7])
            if s: return s
    # fallback WMI
    try:
        out = subprocess.check_output('wmic baseboard get SerialNumber /value',
            shell=True, stderr=subprocess.DEVNULL).decode(errors='ignore')
        for line in out.splitlines():
            if 'SerialNumber=' in line:
                v = line.split('=',1)[1].strip()
                if v: return v
    except: pass
    return 'N/A'

def get_smbios_uuid():
    # Type 1: UUID à offset+8, 16 bytes little-endian
    raw = _read_smbios_raw()
    if raw:
        off = _smbios_find(raw, 1)
        if off is not None and off + 24 <= len(raw):
            u = raw[off+8:off+24]
            # Vérifier que c'est pas que des zéros (firmware non initialisé)
            if any(b != 0 for b in u):
                return (f'{int.from_bytes(u[0:4],"little"):08X}-'
                        f'{int.from_bytes(u[4:6],"little"):04X}-'
                        f'{int.from_bytes(u[6:8],"little"):04X}-'
                        f'{u[8:10].hex().upper()}-{u[10:16].hex().upper()}')
    # fallback WMI (source fiable)
    try:
        out = subprocess.check_output('wmic csproduct get UUID /value',
            shell=True, stderr=subprocess.DEVNULL).decode(errors='ignore')
        for line in out.splitlines():
            if 'UUID=' in line:
                v = line.split('=',1)[1].strip()
                if v: return v
    except: pass
    return 'N/A'


# ─── SMBIOS TABLE PARSER / PATCHER ────────────────────────────────────────────

def _parse_smbios_structs(data: bytes):
    """
    Parse toutes les structures smBIOS.
    Retourne liste de dicts: {type, offset, length, strings_offset, strings_end, strings[]}
    """
    structs = []
    offset = SMBIOS_HEADER
    while offset < len(data) - 4:
        stype  = data[offset]
        length = data[offset + 1]
        if length < 4 or offset + length > len(data):
            break

        # Zone strings: après la partie formatée, jusqu'au double \x00
        str_start = offset + length
        i = str_start
        while i < len(data) - 1:
            if data[i] == 0 and data[i+1] == 0:
                break
            i += 1
        str_end = i + 2  # inclut le double null

        # Parser les strings individuelles
        strings = []
        j = str_start
        while j < i:
            end = j
            while end < i and data[end] != 0:
                end += 1
            strings.append(data[j:end].decode('latin-1'))
            j = end + 1

        structs.append({
            'type':         stype,
            'offset':       offset,
            'length':       length,
            'str_start':    str_start,
            'str_end':      str_end,
            'strings':      strings,  # index 0 = string #1
        })

        if stype == 127:
            break
        offset = str_end

    return structs


def _rebuild_smbios(data: bytes, structs: list, patches: dict) -> bytes:
    """
    Reconstruit le buffer smBIOS avec les strings patchées.
    patches = {(struct_index, string_index_1based): new_string}
    """
    result = bytearray()
    for si, s in enumerate(structs):
        # Partie formatée inchangée
        formatted = bytearray(data[s['offset']:s['offset'] + s['length']])

        # Reconstruire les strings avec patches
        new_strings = list(s['strings'])
        for (pidx, pstr_idx), new_val in patches.items():
            if pidx == si and 1 <= pstr_idx <= len(new_strings):
                new_strings[pstr_idx - 1] = new_val

        # Encoder les strings
        str_bytes = bytearray()
        for st in new_strings:
            str_bytes += st.encode('latin-1', errors='replace') + b'\x00'
        if not str_bytes:
            str_bytes = b'\x00'
        str_bytes += b'\x00'  # double null final

        result += formatted + str_bytes

    return bytes(result)


def _uuid_to_smbios(u: uuid.UUID) -> bytes:
    return (
        u.time_low.to_bytes(4, 'little') +
        u.time_mid.to_bytes(2, 'little') +
        u.time_hi_version.to_bytes(2, 'little') +
        bytes([u.clock_seq_hi_variant, u.clock_seq_low]) +
        u.node.to_bytes(6, 'big')
    )


def patch_smbios(new_cpu, new_bios, new_mb, new_uuid: uuid.UUID):
    """
    Lit SMBiosData, patch CPU/BIOS/MB serials + UUID, réécrit.
    Retourne (True, None) ou (False, error_msg)
    """
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SMBIOS_PATH) as k:
            raw, rtype = winreg.QueryValueEx(k, 'SMBiosData')
    except Exception as e:
        return False, f'Cannot read SMBiosData: {e}'

    data    = bytes(raw)
    structs = _parse_smbios_structs(data)

    # Reconstruire le buffer: garder le header Windows (8 bytes) intact
    result = bytearray(data[:SMBIOS_HEADER])

    for si, s in enumerate(structs):
        formatted = bytearray(data[s['offset']:s['offset'] + s['length']])

        # Patch UUID dans type 1 (System Info), offset +8 dans la partie formatée
        if s['type'] == 1 and len(formatted) >= 24:
            formatted[8:24] = _uuid_to_smbios(new_uuid)

        # Déterminer quelles strings patcher selon le type
        new_strings = list(s['strings'])

        if s['type'] == 0:
            # BIOS Info: string #2 = BIOSVersion
            ver_idx = formatted[5] if len(formatted) > 5 else 0
            if ver_idx > 0 and ver_idx <= len(new_strings):
                new_strings[ver_idx - 1] = new_bios

        elif s['type'] == 1:
            # System Info: Serial = offset+7, UUID = offset+8
            sn_idx = formatted[7] if len(formatted) > 7 else 0
            if sn_idx > 0 and sn_idx <= len(new_strings):
                new_strings[sn_idx - 1] = rand_hex(16)
            
            # UUID patch (16 bytes)
            if len(formatted) >= 24:
                formatted[8:24] = _uuid_to_smbios(new_uuid)

        elif s['type'] == 2:
            # Baseboard: Serial = offset+7
            sn_idx = formatted[7] if len(formatted) > 7 else 0
            if sn_idx > 0 and sn_idx <= len(new_strings):
                new_strings[sn_idx - 1] = new_mb

        elif s['type'] == 3:
            # Chassis/Enclosure: Serial = offset+7
            sn_idx = formatted[7] if len(formatted) > 7 else 0
            if sn_idx > 0 and sn_idx <= len(new_strings):
                new_strings[sn_idx - 1] = rand_hex(16)

        elif s['type'] == 4:
            # Processor: Serial = offset+6
            sn_idx = formatted[6] if len(formatted) > 6 else 0
            if sn_idx > 0 and sn_idx <= len(new_strings):
                new_strings[sn_idx - 1] = new_cpu

        # Encoder
        str_bytes = bytearray()
        for st in new_strings:
            str_bytes += st.encode('latin-1', errors='replace') + b'\x00'
        if not str_bytes:
            str_bytes = b'\x00'
        str_bytes += b'\x00'

        result += bytes(formatted) + bytes(str_bytes)

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SMBIOS_PATH,
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, 'SMBiosData', 0, rtype, bytes(result))
        return True, None
    except Exception as e:
        return False, str(e)


def spoof_mac():
    """Spoof MAC addresses for all network adapters via registry."""
    count = 0
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, NET_CLASS_PATH) as k:
            for i in range(100):
                try:
                    sub_name = winreg.EnumKey(k, i)
                    if sub_name == 'Properties': continue
                    sub_path = f"{NET_CLASS_PATH}\\{sub_name}"
                    # Check if it's a real adapter (has DriverDesc)
                    desc = _reg_get(sub_path, 'DriverDesc')
                    if desc:
                        # Generate random MAC (2nd char must be 2, 6, A, or E for locally administered)
                        mac = f"0{random.choice('26AE')}{rand_hex(10)}"
                        if _reg_set(sub_path, 'NetworkAddress', mac):
                            count += 1
                except OSError: break
    except: pass
    return count

# ─── FLUSH WMI ────────────────────────────────────────────────────────────────

def flush_wmi_cache():
    commands = [
        'net stop winmgmt /y',
        'timeout /t 2 /nobreak >nul',
        'rd /s /q C:\\Windows\\System32\\wbem\\Repository',
        'net start winmgmt',
        'winmgmt /resetrepository',
    ]
    for cmd in commands:
        subprocess.run(cmd, shell=True, capture_output=True)

# ─── SPOOF ALL ────────────────────────────────────────────────────────────────

def spoof_all():
    new_cpu  = rand_hex(16)
    new_bios = rand_hex(16)
    new_mb   = rand_hex(16)
    new_uuid = uuid.uuid4()
    print()

    # 1. Registry patches
    # BIOS / Hardware Description
    _reg_set(BIOS_PATH, 'BIOSVersion',      new_bios)
    _reg_set(BIOS_PATH, 'BaseBoardProduct', new_mb)
    _reg_set(BIOS_PATH, 'SystemSerialNumber', rand_hex(16))
    
    # Machine GUID
    _reg_set(CRIPTO_PATH, 'MachineGuid', str(uuid.uuid4()))
    
    # Hardware Profile GUID
    _reg_set(HW_PROF_PATH, 'HwProfileGuid', f'{{{uuid.uuid4()}}}')
    
    # Windows Product ID
    new_pid = f'{rand_hex(5)}-{rand_hex(5)}-{rand_hex(5)}-{rand_hex(5)}'
    _reg_set(WIN_NT_PATH, 'ProductId', new_pid)

    print(f'  [+] Registry patched (GUIDs, PID, BIOS)')

    # 2. Patch MAC Addresses
    mac_count = spoof_mac()
    print(f'  [+] MAC Addresses: {mac_count} adapters patched')

    # 3. Patch table smBIOS brute (source lue par anti-cheats)
    ok, err = patch_smbios(new_cpu, new_bios, new_mb, new_uuid)
    if ok:
        print(f'  [+] SMBiosData patched')
    else:
        print(f'  [-] SMBiosData: {err}')

    # 3. Flush WMI cache
    print(f'  [*] Flushing WMI cache...')
    flush_wmi_cache()
    print(f'  [+] WMI cache cleared')

    print()
    print(f'  CPU         -> {new_cpu}')
    print(f'  BIOS        -> {new_bios}')
    print(f'  Motherboard -> {new_mb}')
    print(f'  smBIOS UUID -> {str(new_uuid).upper()}')
    print()
    print('  [*] CPU / BIOS / Motherboard : actif maintenant (WMI flushed)')
    print('  [!] smBIOS UUID              : actif apres reboot (kernel memory)')
    print()

# ─── BACKUP ───────────────────────────────────────────────────────────────────

def backup():
    data = {
        'date': datetime.now().isoformat(),
        'cpu':  get_cpu(), 'bios': get_bios(),
        'motherboard': get_motherboard(), 'smbios_uuid': get_smbios_uuid(),
        'smbios_raw': None, 'smbios_rtype': None,
    }
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SMBIOS_PATH) as k:
            raw, rtype = winreg.QueryValueEx(k, 'SMBiosData')
            data['smbios_raw']   = list(bytes(raw))
            data['smbios_rtype'] = rtype
    except: pass
    with open(BACKUP_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'  [+] Backup -> {BACKUP_FILE}')
    print(f'      CPU         : {data["cpu"]}')
    print(f'      BIOS        : {data["bios"]}')
    print(f'      Motherboard : {data["motherboard"]}')
    print(f'      smBIOS UUID : {data["smbios_uuid"]}')

# ─── RESTORE ──────────────────────────────────────────────────────────────────

def restore():
    try:
        with open(BACKUP_FILE) as f: data = json.load(f)
    except FileNotFoundError:
        print('  [-] No backup found.'); return
    print(f'  [*] Restoring from {data["date"]}...\n')
    _reg_set(BIOS_PATH, 'ProcessorId',      data['cpu'])
    _reg_set(BIOS_PATH, 'BIOSVersion',      data['bios'])
    _reg_set(BIOS_PATH, 'BaseBoardProduct', data['motherboard'])
    print(f'  [+] CPU         -> {data["cpu"]}')
    print(f'  [+] BIOS        -> {data["bios"]}')
    print(f'  [+] Motherboard -> {data["motherboard"]}')
    if data.get('smbios_raw'):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SMBIOS_PATH,
                                0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, 'SMBiosData', 0,
                                  data['smbios_rtype'], bytes(data['smbios_raw']))
            print(f'  [+] smBIOS UUID -> {data["smbios_uuid"]}')
        except Exception as e: print(f'  [-] smBIOS: {e}')
    flush_wmi_cache()
    print('\n  [*] Restore done. Reboot recommended.')

# ─── LIST ─────────────────────────────────────────────────────────────────────

def list_ids():
    print()
    print('  Serial Numbers')
    print(f'  CPU         : {get_cpu()}')
    print(f'  BIOS        : {get_bios()}')
    print(f'  Motherboard : {get_motherboard()}')
    print(f'  smBIOS UUID : {get_smbios_uuid()}')
    print()

# ─── MENU ─────────────────────────────────────────────────────────────────────

def main():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', sys.executable, ' '.join(sys.argv), None, 1)
        sys.exit()
    while True:
        print()
        print('  ╔══════════════════════════════════╗')
        print('  ║          HWID SPOOFER            ║')
        print('  ╠══════════════════════════════════╣')
        print('  ║  1. List current IDs             ║')
        print('  ║  2. Backup current IDs           ║')
        print('  ║  3. Change all HWIDs             ║')
        print('  ║  4. Restore from backup          ║')
        print('  ║  0. Exit                         ║')
        print('  ╚══════════════════════════════════╝')
        print()
        choice = input('  > ').strip()
        if   choice == '1': list_ids()
        elif choice == '2': backup()
        elif choice == '3': spoof_all()
        elif choice == '4': restore()
        elif choice == '0': break
        else: print('  [!] Invalid choice.')
        input('\n  Press Enter to continue...')

if __name__ == '__main__':
    main()
