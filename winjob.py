"""Windows Job Object：工作进程结束时由系统清理其全部子进程。"""
import ctypes
from ctypes import wintypes

_job_handle = None


def assign_worker_job():
    global _job_handle
    if _job_handle is not None:
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    size_t = ctypes.c_size_t

    class BasicLimit(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_int64),
            ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', wintypes.DWORD),
            ('MinimumWorkingSetSize', size_t), ('MaximumWorkingSetSize', size_t),
            ('ActiveProcessLimit', wintypes.DWORD), ('Affinity', size_t),
            ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
            'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BasicLimit), ('IoInfo', IoCounters),
                    ('ProcessMemoryLimit', size_t), ('JobMemoryLimit', size_t),
                    ('PeakProcessMemoryUsed', size_t), ('PeakJobMemoryUsed', size_t)]

    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimit()
        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE；句柄不可继承，仅由当前进程持有。
        limits.BasicLimitInformation.LimitFlags = 0x2000
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    except Exception:
        kernel.CloseHandle(handle)
        raise
    _job_handle = handle
