import os
from typing import Dict, List, Optional, Type

from vllm.model_executor.layers.quantization.kernels.scaled_mm.cutlass import (
    CutlassScaledMMLinearKernel)
from vllm.model_executor.layers.quantization.kernels.scaled_mm.xla import (
    XLAScaledMMLinearKernel)

from vllm.model_executor.layers.quantization.kernels.scaled_mm.ScaledMMLinearKernel import (
    ScaledMMLinearKernel, ScaledMMLinearLayerConfig)
from vllm.platforms import current_platform, PlatformEnum

# in priority/performance order (when available)
_POSSIBLE_KERNELS: Dict[PlatformEnum, List[Type[ScaledMMLinearKernel]]] = {
    PlatformEnum.CPU: [CutlassScaledMMLinearKernel],
    PlatformEnum.CUDA: [CutlassScaledMMLinearKernel],
    PlatformEnum.TPU: [XLAScaledMMLinearKernel],
}

def choose_scaled_mm_linear_kernel(
        config: ScaledMMLinearLayerConfig,
        compute_capability: Optional[int] = None) -> Type[ScaledMMLinearKernel]:
    """
    Choose an ScalledMMLinearKernel that can implement the given config for the 
    given compute capability. Attempts to choose the best kernel in terms of 
    performance.

    Args:
        config (ScaledMMLinearLayerConfig): Description of the linear layer 
            to be implemented.
        compute_capability (Optional[int], optional): The compute capability of
            the target device, if None uses `current_platform` to get the 
            compute capability. Defaults to None.

    Raises:
        ValueError: If no kernel can implement the given config.

    Returns:
        Type[ScaledMMLinearKernel]: Chosen kernel.
    """
    
    if compute_capability is None:
        compute_capability = current_platform.get_device_capability()

    failure_reasons = []
    for kernel in _POSSIBLE_KERNELS[current_platform._enum]:
        if kernel.__name__ in os.environ.get("VLLM_DISABLED_KERNELS", "")\
            .split(","):
            failure_reasons.append(
                f' {kernel.__name__} disabled by environment variable')
            continue
        
        if (compute_capability is not None and 
            kernel.get_min_capability() > compute_capability):
            failure_reasons.append(
                f"{kernel.__name__} requires capability "
                f"{kernel.get_min_capability()}, current compute capability "
                f"is {compute_capability}")
            continue

        can_implement, failure_reason = kernel.can_implement(config)
        if can_implement:
            return kernel
        else:
            failure_reasons.append(
                f' {kernel.__name__} cannot implement due to: {failure_reason}'
            )

    raise ValueError(
        "Failed to find a kernel that can implement the "\
        "ScaledMM linear layer. Reasons: \n"
        + '\n'.join(failure_reasons))
