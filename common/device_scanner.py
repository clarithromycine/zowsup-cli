from typing import Any, Optional, Dict, List, Tuple

import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


class DeviceScanner:
    """Android璁惧缃戠粶鎵弿鍣紝璐熻矗鏈湴缃戠粶妫€娴嬪拰ADB璁惧鍙戠幇銆?""
    
    @staticmethod
    def get_local_network_prefixes() -> Any:
        """鑾峰彇鏈満鎵€鏈夌綉缁滄帴鍙ｇ殑IP娈点€?""
        network_prefixes = []
        try:
            # 鑾峰彇鎵€鏈夌綉缁滄帴鍙ｄ俊鎭?
            import socket
            hostname = socket.gethostname()
            
            # 鏂规硶1: 閫氳繃hostname鑾峰彇IP
            try:
                local_ip = socket.gethostbyname(hostname)
                prefix = ".".join(local_ip.split(".")[:-1])
                network_prefixes.append((prefix, local_ip))
                print(f"Local IP: {local_ip}, Network: {prefix}.x")
            except:
                pass
            
            # 鏂规硶2: 閫氳繃socket杩炴帴澶栭儴鍦板潃鏉ヨ幏鍙栨湰鏈篒P
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                prefix = ".".join(local_ip.split(".")[:-1])
                if not any(p[0] == prefix for p in network_prefixes):
                    network_prefixes.append((prefix, local_ip))
                    print(f"Local IP (via socket): {local_ip}, Network: {prefix}.x")
            except:
                pass
            
            # 濡傛灉杩樻槸娌℃湁鎵惧埌锛屼娇鐢ㄩ粯璁ゅ€?
            if not network_prefixes:
                print("Could not determine local network, using 192.168.1.x")
                network_prefixes.append(("192.168.1", "192.168.1.0"))
                
        except Exception as e:
            print(f"Error detecting network: {e}, using 192.168.1.x")
            network_prefixes.append(("192.168.1", "192.168.1.0"))
        
        return network_prefixes

    @staticmethod
    def check_adb_device(ip, timeout=2) -> Any:
        """妫€鏌ュ崟涓狪P鏄惁鏈堿DB璁惧锛岃繑鍥濱P鎴朜one銆?""
        ip_with_port = f"{ip}:5555"
        try:
            result = subprocess.run(
                ["adb", "connect", ip_with_port],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
                return ip_with_port
        except Exception as e:
            pass
        return None

    @staticmethod
    def parse_network_prefix(network_input) -> Any:
        """瑙ｆ瀽鍜岃鑼冨寲缃戞杈撳叆锛屾敮鎸丆IDR琛ㄧず娉曘€?
        
        鏀寔澶氱鏍煎紡锛?
        - 192.168.100 (C绫荤綉娈?
        - 192.168.100.0 (缃戞鍦板潃)
        - 192.168.100.0/24 (CIDR鏍煎紡 - 鍗曚釜C绫荤綉娈?
        - 192.168.100.0/23 (CIDR鏍煎紡 - 涓や釜C绫荤綉娈?
        - 192.168.100.0/25 (CIDR鏍煎紡 - C绫荤綉娈电殑涓€鍗?
        - 192.168.100.* (閫氶厤绗︽牸寮?
        
        Returns:
            list: 鍖呭惈涓€涓垨澶氫釜缃戞鍓嶇紑鐨勫垪琛紝濡俒'192.168.100', '192.168.101']
        """
        if not network_input:
            return None
        
        network_input = network_input.strip()
        
        # 绉婚櫎鏈熬鐨勭偣鍙?
        if network_input.endswith('.'):
            network_input = network_input[:-1]
        
        # 澶勭悊閫氶厤绗︽牸寮?(192.168.100.*)
        if network_input.endswith('.*'):
            network_input = network_input[:-2]
        
        # 澶勭悊CIDR鏍煎紡 (192.168.100.0/24)
        if '/' in network_input:
            try:
                ip_part, mask = network_input.split('/')
                mask = int(mask)
                
                # 灏咺P杞崲涓?2浣嶆暣鏁?
                parts = ip_part.split('.')
                if len(parts) != 4:
                    print(f"Invalid IP format: {ip_part}")
                    return None
                
                ip_int = (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
                
                # 鍒涘缓鎺╃爜
                mask_int = (0xffffffff << (32 - mask)) & 0xffffffff
                
                # 鑾峰彇缃戞鐨勮捣濮婭P
                network_int = ip_int & mask_int
                
                # 鑾峰彇缃戞鐨勫箍鎾璉P
                broadcast_int = network_int | (~mask_int & 0xffffffff)
                
                # 鐢熸垚缃戞鍓嶇紑鍒楄〃
                prefixes = set()
                current_ip = network_int
                
                # 鏀堕泦鎵€鏈夎鐩栫殑C绫荤綉娈靛墠缂€
                while current_ip <= broadcast_int:
                    # 鎻愬彇鍓嶄笁涓叓浣嶆暟锛圕绫荤綉娈电殑鍓嶇紑锛?
                    third_octet = (current_ip >> 8) & 0xff
                    first_octet = (current_ip >> 24) & 0xff
                    second_octet = (current_ip >> 16) & 0xff
                    
                    prefix = f"{first_octet}.{second_octet}.{third_octet}"
                    prefixes.add(prefix)
                    
                    # 绉诲埌涓嬩竴涓狪P
                    current_ip += 1
                
                prefixes = sorted(list(prefixes))
                
                if prefixes:
                    print(f"Parsed CIDR {ip_part}/{mask} to {len(prefixes)} network prefix(es): {', '.join(prefixes)}")
                    return prefixes
                else:
                    return None
                    
            except ValueError as e:
                print(f"Invalid CIDR format: {network_input}, error: {e}")
                return None
        
        # 澶勭悊鏍囧噯鏍煎紡 (192.168.100.0 鎴?192.168.100)
        parts = network_input.split('.')
        if len(parts) == 4:
            # 绉婚櫎绗洓涓叓浣嶆暟
            network_input = '.'.join(parts[:3])
        elif len(parts) == 3:
            # 宸茬粡鏄爣鍑嗘牸寮?
            pass
        else:
            print(f"Invalid network format: {network_input}")
            return None
        
        return [network_input]

    @staticmethod
    def scan_network_for_devices(network_prefix=None, timeout=2, max_workers=50) -> Any:
        """浣跨敤澶氱嚎绋嬫壂鎻忔湰鍦扮綉缁滀腑鐨凙ndroid璁惧銆?
        
        Args:
            network_prefix: 鎸囧畾缃戞鍓嶇紑锛屾敮鎸佸绉嶆牸寮忥細
                           - 192.168.100 (C绫荤綉娈?
                           - 192.168.100.0 (缃戞鍦板潃)
                           - 192.168.100.0/24 (CIDR鏍煎紡 - 鍗曚釜C绫荤綉娈?
                           - 192.168.100.0/23 (CIDR鏍煎紡 - 涓や釜C绫荤綉娈?
                           - 192.168.100.* (閫氶厤绗︽牸寮?
                           濡傛灉涓篘one鍒欒嚜鍔ㄦ娴嬫湰鏈虹綉娈?
            timeout: 鍗曚釜IP鐨勮秴鏃舵椂闂达紙绉掞級
            max_workers: 绾跨▼鏁?
        """
        print("Scanning local network for Android devices (using multi-threading)...")
        found_devices = []
        
        # 纭畾瑕佹壂鎻忕殑缃戞
        if network_prefix is None:
            # 鑷姩妫€娴嬫湰鏈虹綉娈?
            network_prefixes = DeviceScanner.get_local_network_prefixes()
            prefixes_to_scan = [prefix for prefix, _ in network_prefixes]
        else:
            # 浣跨敤鎸囧畾鐨勭綉娈碉紝杩涜瑙勮寖鍖?
            parsed_prefixes = DeviceScanner.parse_network_prefix(network_prefix)
            if parsed_prefixes is None:
                print("Failed to parse network prefix, using auto-detection instead")
                network_prefixes = DeviceScanner.get_local_network_prefixes()
                prefixes_to_scan = [prefix for prefix, _ in network_prefixes]
            else:
                prefixes_to_scan = parsed_prefixes
        
        # 鏋勫缓鎵€鏈夐渶瑕佹鏌ョ殑IP鍦板潃
        ips_to_check = []
        for prefix in prefixes_to_scan:
            for i in range(1, 255):
                ips_to_check.append(f"{prefix}.{i}")
        
        print(f"Checking {len(ips_to_check)} IP addresses with {max_workers} threads...")
        
        # 浣跨敤ThreadPoolExecutor杩涜澶氱嚎绋嬫壂鎻?
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(DeviceScanner.check_adb_device, ip, timeout): ip for ip in ips_to_check}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    found_devices.append(result)
                    print(f"Found device: {result}")
        return found_devices
