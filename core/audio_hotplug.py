"""Observe Windows endpoints without opening or recording audio streams."""
import platform


def endpoint_snapshot():
    if platform.system() != 'Windows':
        import sounddevice as sd
        devices=sd.query_devices()
        signature=tuple((d['name'],d['max_input_channels'],d['max_output_channels']) for d in devices)
        return (signature,tuple(sd.default.device))
    import comtypes
    comtypes.CoInitialize()
    try:
        return _windows_snapshot()
    finally:
        comtypes.CoUninitialize()


def _windows_snapshot():
    import winreg
    from pycaw.utils import AudioUtilities
    enumerator=AudioUtilities.GetDeviceEnumerator()
    active=[]
    defaults=[]
    for direction in (0,1):
        collection=enumerator.EnumAudioEndpoints(direction,1)
        ids=tuple(sorted(collection.Item(i).GetId() for i in range(collection.GetCount())))
        active.append(ids)
        for role in (0,1):
            try:
                defaults.append(enumerator.GetDefaultAudioEndpoint(direction,role).GetId())
            except Exception:
                defaults.append(None)
    permissions=[]
    path=r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone'
    for root,suffix in ((winreg.HKEY_LOCAL_MACHINE,''),(winreg.HKEY_CURRENT_USER,''),(winreg.HKEY_CURRENT_USER,r'\NonPackaged')):
        try:
            with winreg.OpenKey(root,path+suffix) as key:
                permissions.append(winreg.QueryValueEx(key,'Value')[0])
        except OSError:
            permissions.append(None)
    return (tuple(active),tuple(defaults),tuple(permissions))


class ChangeTracker:
    """Require two identical new observations to settle a device change."""
    def __init__(self):
        self.current=None
        self.pending=None

    def observe(self,snapshot):
        if self.current is None:
            self.current=snapshot
            return False
        if snapshot==self.current:
            self.pending=None
            return False
        if snapshot==self.pending:
            self.current=snapshot
            self.pending=None
            return True
        self.pending=snapshot
        return False
