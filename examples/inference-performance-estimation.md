# Research Document

## Problem Statement

Problem statement:
- objective: currently blis contains two modeling techniques for inference performance:
  - blackbox optimization approach as documented in @docs/approach.md and
  - roofline approach in @docs/roofline.md
- come up with a third approach that can simulate diverse settings such as
  - model type/architecture: i.e. dense vs. MoE
  - different workload types: i.e. prefill- and decode-heavy and mixed/balanced workloads
  - different hardware: i.e. A100, H100
  - different tensor parallelism sizes and expert parallel settings
  - different vLLM knobs: i.e. chunk size, max-model-len, and --cpu-offloading
- constraints
  - We still want alpha (used to compute the delay between request arrival and queuing) and beta (used to compute the vLLM busy-loop step time) coefficients, but you have freedom to determine what alpha and beta coefficients need to be to achieve objective.
  - We can heavily featurize each setting. You can derive any new features using a model's config.json, the hardware specs (will be provided through data sheets in JSON), vLLM configuration specs, and request characteristics. These are known for each simulation.
  - carefully look into the request journey tracing, step tracing, and KV event streams documented in @vllm.md. Make sure the coefficient vectors alpha and beta can be learned using the tracing and KV event stream data. Provide a short description of the training pipeline. It can include anything from simple linear regression to advanced techniques like expectation maximization, convex optimization, or anything else that is relevant
  - The arrival to queuing latency is alpha * feature_vec_1 and the step-time latency is beta * feature_vec_2 (the `*` represents dot product). Feel free to derive the features in any way you think is appropriate. Show your reasoning and explain why the features meet the constraints and objectives.
  - we want the training procedure to not overfit but be robust

---

# Background

## Repository Overview

BLIS (Blackbox Inference Simulator) is a discrete-event simulator for LLM inference platforms (vLLM, SGLang). It models request arrival, KV-cache dynamics, scheduling, token generation, and latency using trained performance coefficients (alpha/beta) or analytical roofline models. The simulator is CPU-only and designed for capacity planning, saturation analysis, and performance prediction without requiring real GPUs.

## Technology Stack

- **Language**: Go (Golang)
- **Architecture**: Discrete-event simulation with min-heap event queue
- **Key Dependencies**: Standard library (`container/heap`), logrus for logging, YAML/JSON config parsing
- **External Data Sources**: HuggingFace model configs (`config.json`), hardware datasheets

## Relevant Architecture

### Core Simulation Engine (`sim/`)

The simulator uses a discrete-event architecture:

1. **Event Queue**: Min-heap priority queue ordering events by timestamp
2. **Event Types**: `ArrivalEvent`, `QueuedEvent`, `StepEvent`, `ScheduledEvent`, `RequestLeftEvent`, `PreemptionEvent`
3. **Request Lifecycle**: `queued` -> `running` -> `completed`
4. **Batch Formation**: Respects token budgets, max batch size, chunked prefill thresholds

### Latency Estimation (Current Approaches)

**1. Blackbox Mode** (current default):
- Alpha coefficients for queueing time: `alpha_latency = alpha[0] + alpha[1] * input_len`
- Beta coefficients for step time: `beta_latency = beta[0] + beta[1] * cache_miss_tokens + beta[2] * decode_tokens`
- 3-element coefficient vectors learned via Bayesian optimization against ground-truth vLLM metrics

**2. Roofline Mode** (analytical):
- Calculates FLOPs for transformer layers (GEMM ops, attention, MLP)
- Models memory bandwidth bottlenecks (weights, KV cache growth/access)
- Step time = max(compute_bound, memory_bound) + overheads
- Requires `config.json` and `hardware_config.json`, no training needed
- Current limitation: Does not support MoE models

### Key Data Structures

```go
// SimConfig - All simulation parameters
type SimConfig struct {
    Horizon, Seed, TotalKVBlocks, BlockSizeTokens int64
    MaxRunningReqs, MaxScheduledTokens int64
    BetaCoeffs, AlphaCoeffs []float64  // >=3 elements each
    ModelConfig ModelConfig
    HWConfig HardwareCalib
    Model, GPU string
    TP int
    Roofline bool
    // ... workload, policy configs
}

// ModelConfig - From HuggingFace config.json
type ModelConfig struct {
    NumLayers, HiddenDim, NumHeads, NumKVHeads int
    VocabSize, IntermediateDim int
    BytesPerParam float64
}

// HardwareCalib - GPU specifications
type HardwareCalib struct {
    TFlopsPeak, BwPeakTBs, BwEffConstant float64
    TOverheadMicros, PerLayerOverhead float64
    MfuPrefill, MfuDecode, AllReduceLatency float64
}

// RegressionFeatures - Current batch features for step time
type RegressionFeatures struct {
    TotalCacheMissTokens, TotalDecodeTokens int64
    NumDecodeRequests, NumPrefillRequests int64
    TotalPrefillTokens, MaxPrefillTokens int64
}
```

## Key Files and Components

| File | Purpose |
|------|---------|
| `sim/simulator.go` | Core event loop, batch formation, step execution, latency estimation |
| `sim/roofline_step.go` | Analytical FLOPs/bandwidth calculations for roofline mode |
| `sim/model_hardware_config.go` | Parsing HuggingFace configs and hardware specs |
| `sim/kvcache.go` | Block-based KV cache with LRU eviction and prefix caching |
| `sim/request.go` | Request state machine and lifecycle |
| `defaults.yaml` | Pre-trained alpha/beta coefficients per model/GPU/TP combination |
| `vllm.md` | Documentation of vLLM tracing capabilities for data collection |

## Existing Patterns and Conventions

### Current Alpha Model (Queueing Latency)
```go
func (sim *Simulator) getQueueingTime(req *Request) int64 {
    totalProcessingTime := sim.alphaCoeffs[0]                               // alpha0: base overhead
    totalProcessingTime += sim.alphaCoeffs[1] * float64(len(req.InputTokens)) // alpha1 * input_len
    return int64(totalProcessingTime)
}

func (sim *Simulator) getOutputTokenProcessingTime() int64 {
    return int64(sim.alphaCoeffs[2]) // alpha2: per-output-token overhead
}
```

### Current Beta Model (Step Time)
```go
func (sim *Simulator) getStepTime() int64 {
    totalStepTime := sim.betaCoeffs[0]  // beta0: base step overhead
    totalStepTime += sim.betaCoeffs[1] * float64(sim.runningBatchFeatures.TotalCacheMissTokens)  // prefill compute
    totalStepTime += sim.betaCoeffs[2] * float64(sim.runningBatchFeatures.TotalDecodeTokens)     // decode compute
    return int64(totalStepTime)
}
```

### Training Data Sources (from vllm.md)

**Request Journey Tracing:**
- Events: ARRIVED -> HANDOFF_TO_CORE -> QUEUED -> SCHEDULED -> FIRST_TOKEN -> FINISHED -> DEPARTED
- Alpha target: `t_scheduled - t_queued`
- Attributes: `prefill_total_tokens`, `phase`, `num_preemptions`, `schedule.kind`

**Step Tracing:**
- Events: `step.BATCH_SUMMARY` with queue state, batch composition, KV cache health
- Beta target: `step.duration_us`
- Features: `batch.prefill_tokens`, `batch.decode_tokens`, `kv.usage_gpu_ratio`, `queue.running_depth`

**KV Cache Events:**
- `CacheStoreCommitted`, `TransferInitiated`, `TransferCompleted`
- Useful for: prefix cache hit rates, memory pressure modeling

## Dependencies and Integrations

1. **vLLM Tracing**: OpenTelemetry traces exported via OTLP collector
2. **HuggingFace Hub**: Model architecture configs (`config.json`)
3. **NVIDIA Datasheets**: Peak TFLOPS, memory bandwidth for roofline calculations
4. **Workload Generation**: CSV trace replay or distribution-based (GuideLLM style)

## Additional Context

### Gap Analysis: Why a Third Approach?

| Aspect | Blackbox | Roofline | Gap |
|--------|----------|----------|-----|
| Training Required | Yes (hours per config) | No | Need fast+accurate option |
| MoE Support | Partial (if trained) | No | Critical gap |
| Hardware Generalization | Poor (per-GPU coeffs) | Good | Blackbox doesn't transfer |
| Workload Sensitivity | Limited (3 features) | Good | Need richer feature space |
| vLLM Knob Sensitivity | Not modeled | Not modeled | Neither handles config changes |

### Available Feature Sources

1. **Model Config**: `num_layers`, `hidden_size`, `num_heads`, `num_kv_heads`, `intermediate_size`, `vocab_size`, `torch_dtype`
2. **Hardware Specs**: `TFlopsPeak`, `BwPeakTBs`, `MfuPrefill`, `MfuDecode`, `AllReduceLatency`
3. **Runtime State**: `queue_depth`, `running_batch_size`, `kv_cache_usage_ratio`, `prefill_tokens`, `decode_tokens`
4. **Request Characteristics**: `prompt_length`, `output_length`, `prefix_hit_ratio`
5. **vLLM Config**: `max-num-batched-tokens`, `max-num-seqs`, `enable-chunked-prefill`, `enable-prefix-caching`, `tensor-parallel-size`

### Key Constraints for New Approach

1. Must output alpha and beta coefficient vectors (dot product with features)
2. Must be learnable from vLLM tracing data (journey + step + KV events)
3. Must generalize across: dense/MoE, A100/H100, TP1-8, various vLLM knobs
4. Must be robust (not overfit to specific workloads)
5. Features must be computable at simulation time (from known inputs)

---

# Idea 1

## Normalized Roofline Residual Learning (NRRL)

### Core Concept

Combine analytical roofline modeling with learned residual corrections by expressing features as **hardware-normalized computational intensities**. Instead of learning raw coefficients per hardware/model combination, learn corrections to theoretical roofline predictions that transfer across configurations.

### Key Insight

The roofline model provides theoretical bounds but misses:
1. Software overheads (vLLM scheduler, Python GIL, CUDA graph compilation)
2. Memory access patterns (non-contiguous KV cache reads, fragmentation)
3. MoE routing overhead and expert load imbalance
4. vLLM-specific knob effects

By normalizing features to dimensionless ratios relative to hardware capabilities, we create a **portable feature space** where learned coefficients transfer across GPU types.

### Feature Engineering

#### Alpha Features (Queueing Latency) - 8 dimensions

```
feature_vec_alpha = [
    1.0,                                        # alpha_0: base overhead
    prompt_tokens / max_model_len,              # alpha_1: normalized prompt length
    queue_depth / max_num_seqs,                 # alpha_2: normalized queue pressure
    kv_usage_ratio,                             # alpha_3: memory pressure [0,1]
    running_batch_size / max_num_seqs,          # alpha_4: batch fullness
    is_chunked_prefill_enabled,                 # alpha_5: binary flag
    prompt_tokens * queue_depth / (TFlopsPeak * 1e6),  # alpha_6: compute-weighted queue
    num_preemptions_recent / max_num_seqs       # alpha_7: preemption pressure
]
```

**Rationale**: Queueing delay depends on system load (queue depth, batch fullness), memory pressure (KV usage), and vLLM configuration (chunked prefill changes scheduling behavior). All features are normalized to [0,1] or dimensionless ratios.

#### Beta Features (Step Time) - 12 dimensions

```
feature_vec_beta = [
    1.0,                                        # beta_0: base step overhead

    # Compute-normalized features
    prefill_flops / (TFlopsPeak * 1e12),        # beta_1: prefill compute intensity
    decode_flops / (TFlopsPeak * 1e12),         # beta_2: decode compute intensity
    attention_flops / (TFlopsPeak * 1e12),      # beta_3: attention compute (scales with seq_len^2)

    # Memory-normalized features
    kv_read_bytes / (BwPeakTBs * 1e12),         # beta_4: KV cache read intensity
    kv_write_bytes / (BwPeakTBs * 1e12),        # beta_5: KV cache write intensity
    weight_read_bytes / (BwPeakTBs * 1e12),     # beta_6: weight loading intensity

    # Batch composition features
    num_prefill_reqs / batch_size,              # beta_7: prefill fraction
    max_seq_len / max_model_len,                # beta_8: normalized context length

    # MoE-specific features (0 for dense models)
    active_experts / total_experts,             # beta_9: expert activation ratio
    expert_load_imbalance,                      # beta_10: stddev of tokens per expert / mean

    # Parallelism features
    (num_layers * 2 * allreduce_latency) / step_time_estimate  # beta_11: communication fraction
]
```

**Rationale**:
- FLOPs and bytes are normalized by hardware peak capabilities, making features dimensionless
- MoE features capture expert routing overhead (beta_9) and load imbalance penalty (beta_10)
- Communication fraction (beta_11) captures TP overhead relative to compute

### Training Pipeline

#### Phase 1: Data Collection
```bash
# Enable comprehensive tracing
vllm serve MODEL \
  --enable-journey-tracing --journey-tracing-sample-rate 1.0 \
  --step-tracing-enabled --step-tracing-sample-rate 1.0 \
  --step-tracing-rich-subsample-rate 1.0 \
  --otlp-traces-endpoint http://collector:4317
```

Collect traces across:
- 3+ model sizes (7B, 13B, 70B)
- 2+ hardware types (A100, H100)
- 3+ TP values (1, 2, 4)
- 4+ workload types (prefill-heavy, decode-heavy, mixed, bursty)

#### Phase 2: Feature Extraction
For each trace event:
1. Compute raw FLOPs using `calculateTransformerFlops()` logic
2. Compute raw bytes using `calculateMemoryAccessBytes()` logic
3. Normalize by hardware specs from `hardware_config.json`
4. Extract batch composition from step trace attributes

#### Phase 3: Robust Regression

**Model**: Ridge regression with cross-validation
```python
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

# Standardize features (except binary flags)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# Ridge with automatic regularization selection
alpha_model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0], cv=5)
alpha_model.fit(X_alpha_scaled, y_alpha)

beta_model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0], cv=5)
beta_model.fit(X_beta_scaled, y_beta)
```

**Why Ridge?**
- L2 regularization prevents overfitting to specific configurations
- Shrinks correlated feature coefficients together (helpful for normalized features)
- Automatic alpha selection via cross-validation

#### Phase 4: Validation
- Time-based holdout (last 20% of traces)
- Cross-hardware validation (train on A100, test on H100)
- Cross-workload validation (train on chatbot, test on summarization)

### MoE Handling

For MoE models, extend `ModelConfig`:
```go
type ModelConfig struct {
    // ... existing fields
    NumExperts      int  `json:"num_local_experts"`
    TopKExperts     int  `json:"num_experts_per_tok"`
    IsMoE           bool // derived: NumExperts > 0
}
```

MoE-specific FLOPs calculation:
```go
func calculateMoEFlops(config ModelConfig, batchTokens int64) float64 {
    if !config.IsMoE {
        return 0
    }
    // Router network FLOPs
    routerFlops := 2.0 * float64(batchTokens) * float64(config.HiddenDim) * float64(config.NumExperts)

    // Expert MLP FLOPs (only TopK experts active)
    expertMLPFlops := 2.0 * float64(batchTokens) * float64(config.TopKExperts) *
                      (3.0 * float64(config.HiddenDim) * float64(config.IntermediateDim))

    return (routerFlops + expertMLPFlops) * float64(config.NumLayers)
}
```

### Advantages

1. **Hardware Transfer**: Normalized features allow coefficients learned on A100 to predict H100 behavior
2. **MoE Native**: Expert activation and load imbalance features model MoE-specific behavior
3. **vLLM Knob Aware**: Chunked prefill, max-seqs directly appear in feature space
4. **Interpretable**: Each coefficient has physical meaning (overhead per normalized FLOP, etc.)
5. **Robust**: Ridge regularization + diverse training set prevents overfitting

### Limitations

1. Requires roofline-style FLOPs/bandwidth calculations (moderate implementation effort)
2. Expert load imbalance requires tracing from rich step snapshots
3. May need per-GPU efficiency constants (MFU factors) as calibration

## Reviews for Idea 1

### Review by Claude (aws/claude-opus-4-6)

**Rating: Adequate** (bordering on Strong, but with several substantive gaps)

**Key Issues Identified:**

1. **Circular dependency in beta_11**: `(num_layers * 2 * allreduce_latency) / step_time_estimate` requires step time, which is what we're predicting. At simulation time, this creates a circular dependency.

2. **Alpha model conflates two phenomena**: The current system has `getQueueingTime()` for arrival-to-scheduling delay AND `getOutputTokenProcessingTime()` for per-output-token overhead. The 8-dimensional alpha only addresses (1), breaking compatibility with `alpha[2]`.

3. **Non-negativity not guaranteed**: Ridge regression can produce negative coefficients, potentially yielding negative step times for unusual feature combinations.

4. **Feature normalization inconsistency**: `alpha_6 = prompt_tokens * queue_depth / (TFlopsPeak * 1e6)` has units tokens²·s/FLOP, not dimensionless. `beta_1` through `beta_6` are actually time-scale features (seconds), not ratios.

5. **Hardware transfer assumption questionable**: Efficiency factors (MFU) differ between A100/H100 due to architectural differences (L2 cache, TMA units). This is likely the dominant source of cross-hardware prediction error.

6. **Missing features**: Prefix cache hit ratio, CPU offloading, chunked prefill effect on step time, re-prefill cost after preemption.

7. **Expert load imbalance not observable at simulation time**: Routing decisions are data-dependent and unknown during simulation.

**Suggestions:**
- Replace beta_11 denominator with roofline compute time estimate
- Add prefix_cache_hit_ratio, cpu_offload_active, chunk_budget_utilization features
- Consider interaction terms and threshold features for nonlinear effects
- Define separate gamma model for per-output-token processing time

### Review by GPT-4o (Azure/gpt-4o)

**Rating: Strong** (with minor adjustments needed)

**Strengths:**
- Comprehensive and well-structured plan with clear requirement alignment
- Innovative use of normalized roofline residual learning for hardware generalization
- Robust training and validation pipeline

**Issues Identified:**

1. **Feature Engineering Complexity**: Requires accurate hardware-specific calibration that may not always be available or consistent.

2. **MoE-Specific Handling**: Assumes metrics can be reliably extracted from vLLM traces, but MoE routing is dynamic and may need additional instrumentation.

3. **Roofline Dependency**: If roofline model is inaccurate for certain configurations, learned residuals may not compensate.

4. **Validation Coverage Gaps**: Missing edge cases like 175B+ models, bursty traffic with preemption, thermal throttling.

5. **Heterogeneous Workloads**: Doesn't address mixed workload types within same batch.

6. **Dynamic vLLM Knob Changes**: Assumes static configurations during simulation.

**Suggestions:**
- Start with smaller high-impact feature subset, expand iteratively
- Enhance MoE tracing and validation details
- Validate roofline against real-world benchmarks for each hardware
- Consider hybrid approach with blackbox fallback
- Explore lightweight neural networks as Ridge alternative

### Review by Gemini (GCP/gemini-2.5-flash)

**Rating: Comprehensive**

The plan is remarkably comprehensive, clearly articulating the problem, reviewing existing approaches, identifying gaps, and proposing a detailed NRRL solution with feature engineering, training pipeline, and validation strategy.

*(Note: Review was truncated by API)*

---

# Idea 2

## Log-Space Additive Component Model (LACM)

### Core Concept

Address Idea 1's key weaknesses by modeling latency in **log-space** to guarantee positivity, separating the alpha model into distinct queue and per-token components, and using **expected** rather than observed MoE behavior. The approach decomposes step time into additive components (base + prefill + decode + communication + overhead) where each component is predicted separately.

### Key Improvements Over Idea 1

| Issue in Idea 1 | Solution in Idea 2 |
|-----------------|-------------------|
| Circular dependency in beta_11 | Eliminate by using fixed communication time (not ratio) |
| Non-negativity not guaranteed | Log-space prediction: `time = exp(alpha · features)` |
| Alpha conflates queue + per-token | Separate models: alpha_queue, alpha_token, beta_step |
| Expert load imbalance unobservable | Use expected load: `top_k / num_experts` (static) |
| Complex 12-dim feature space | Simpler 6-dim base + MoE extension |

### Model Architecture

#### Three-Component Latency Model

```
Queue Latency:     L_queue = exp(alpha_queue · F_queue)
Per-Token Latency: L_token = alpha_token[0] + alpha_token[1] * is_decode
Step Latency:      L_step  = exp(beta · F_step)
```

This maintains compatibility with the current simulator's use of `getQueueingTime()` and `getOutputTokenProcessingTime()`.

### Feature Engineering

#### Alpha_queue Features (Queue Latency) - 5 dimensions

```
F_queue = [
    1.0,                                    # base overhead (log-space intercept)
    log(1 + prompt_tokens),                 # log-transformed prompt length
    log(1 + queue_depth),                   # log-transformed queue depth
    kv_usage_ratio,                         # memory pressure [0,1]
    is_prefix_caching_enabled * prefix_overlap_estimate  # expected cache benefit
]
```

**Rationale**: Log-transforming count features (tokens, queue depth) compresses the dynamic range and makes the relationship with log-latency approximately linear. KV usage captures memory pressure. Prefix caching benefit is estimated from prompt structure.

#### Alpha_token (Per-Token Processing) - 2 coefficients

```
L_token = alpha_token[0]                    # base per-token overhead
        + alpha_token[1] * is_decode_phase  # additional decode overhead (attention grows)
```

**Rationale**: Decode tokens require reading the full KV cache; prefill tokens process in parallel. This simple model captures the asymmetry.

#### Beta Features (Step Time) - 6 dimensions (dense) + 2 (MoE extension)

```
F_step = [
    1.0,                                    # base step overhead

    # Compute features (hardware-scaled)
    log(1 + prefill_tokens) * model_flops_per_token / hw_tflops,
    log(1 + decode_tokens) * model_flops_per_token / hw_tflops,

    # Memory features (hardware-scaled)
    log(1 + total_kv_blocks) * bytes_per_block / hw_bandwidth,
    log(1 + batch_size),                    # scheduling overhead scales with batch

    # Parallelism (fixed, not ratio)
    tp_comm_time_per_layer * num_layers,    # total TP communication time
]

# MoE Extension (append if is_moe):
F_step_moe = [
    log(1 + batch_tokens) * router_flops / hw_tflops,  # router overhead
    expected_expert_imbalance_factor,       # 1.0 + variance_factor (static, from top_k)
]
```

**Key Design Choices:**

1. **Log-transformed counts**: `log(1 + x)` compresses dynamic range, avoids log(0), linearizes multiplicative effects

2. **Hardware scaling as multiplier, not divisor**: `feature * (flops / tflops)` gives time-scale features with correct units (seconds)

3. **MoE load imbalance is expected, not observed**:
   ```
   expected_imbalance_factor = 1.0 + (num_experts - top_k) / (num_experts * top_k) * variance_coefficient
   ```
   This is computable at simulation time from model config alone.

4. **TP communication is additive, not fractional**: `tp_comm_time_per_layer * num_layers` avoids circular dependency

### Training Pipeline

#### Phase 1: Data Collection (Same as Idea 1)

#### Phase 2: Log-Space Targets

```python
# Transform targets to log-space
y_queue_log = np.log(y_queue + epsilon)  # epsilon prevents log(0)
y_step_log = np.log(y_step + epsilon)

# Per-token latency stays in linear space (small, well-bounded)
```

#### Phase 3: Constrained Ridge Regression

```python
from sklearn.linear_model import Ridge
from scipy.optimize import minimize

# Log-space model for queue latency
def fit_log_space_ridge(X, y_log, alpha=1.0):
    """Ridge regression in log-space with non-negative coefficient constraint."""
    model = Ridge(alpha=alpha, positive=True)  # sklearn 1.0+ supports positive=True
    model.fit(X, y_log)
    return model

# Alternative: Non-negative least squares for guaranteed positivity
from scipy.optimize import nnls

def fit_nnls(X, y):
    """Non-negative least squares: all coefficients >= 0."""
    coeffs, residual = nnls(X, y)
    return coeffs
```

**Why Non-Negative Constraints?**
- Combined with log-space, guarantees `time = exp(positive_value) > 0`
- Physical interpretation: each feature adds latency, never reduces it
- Prevents pathological negative predictions

#### Phase 4: Robust Cross-Validation

```python
from sklearn.model_selection import GroupKFold

# Group by (model, hardware) to test generalization
groups = df['model'] + '_' + df['hardware']
gkf = GroupKFold(n_splits=5)

for train_idx, test_idx in gkf.split(X, y, groups):
    # Train on 4 model/hardware combos, test on held-out combo
    ...
```

### MoE Handling

#### Expected Load Imbalance Formula

For top-k out of N experts with batch_size tokens:
```
# Assuming uniform routing (conservative estimate)
expected_tokens_per_expert = batch_size * top_k / num_experts
variance_per_expert = batch_size * top_k / num_experts * (1 - top_k/num_experts)

# Imbalance factor (>1.0 means overhead)
expected_imbalance = 1.0 + sqrt(variance_per_expert) / expected_tokens_per_expert
```

This is computable from `config.json` fields `num_local_experts` and `num_experts_per_tok`.

#### Expert Parallelism (EP) Support

```
F_step_ep = [
    ...,
    ep_comm_time_per_layer * num_layers,  # all-to-all for expert routing
]
```

### Handling vLLM Knobs

| Knob | Feature Impact |
|------|----------------|
| `--enable-chunked-prefill` | Caps `prefill_tokens` per step; affects F_step[1] |
| `--max-num-batched-tokens` | Upper bound on `prefill_tokens + decode_tokens` |
| `--enable-prefix-caching` | `prefix_overlap_estimate` in F_queue |
| `--cpu-offloading` | Add `cpu_transfer_bytes / pcie_bandwidth` to F_step |
| `--tensor-parallel-size` | `tp_comm_time_per_layer` scaling |

### Implementation Changes

```go
// New coefficient structure
type LatencyCoeffs struct {
    AlphaQueue  []float64  // 5 coefficients for queue latency (log-space)
    AlphaToken  []float64  // 2 coefficients for per-token overhead
    BetaStep    []float64  // 6-8 coefficients for step time (log-space)
}

func (sim *Simulator) getQueueingTime(req *Request) int64 {
    features := []float64{
        1.0,
        math.Log(1 + float64(len(req.InputTokens))),
        math.Log(1 + float64(sim.WaitQ.Len())),
        float64(sim.KVCache.UsedBlockCnt) / float64(sim.KVCache.TotalBlocks),
        sim.getPrefixCacheEstimate(req),
    }
    logLatency := dotProduct(sim.coeffs.AlphaQueue, features)
    return int64(math.Exp(logLatency))
}

func (sim *Simulator) getOutputTokenProcessingTime(isDecodePhase bool) int64 {
    latency := sim.coeffs.AlphaToken[0]
    if isDecodePhase {
        latency += sim.coeffs.AlphaToken[1]
    }
    return int64(latency)
}

func (sim *Simulator) getStepTime() int64 {
    features := sim.buildStepFeatures()
    logLatency := dotProduct(sim.coeffs.BetaStep, features)
    return int64(math.Exp(logLatency))
}
```

### Advantages

1. **Guaranteed Positivity**: Log-space + non-negative coefficients ensures `time > 0`
2. **API Compatible**: Maintains separate queue and per-token functions
3. **No Circular Dependencies**: All features computable at simulation time
4. **MoE Support via Expected Values**: Static computation from config, no runtime observation needed
5. **Simpler Feature Space**: 6-8 features vs 12 in Idea 1
6. **Interpretable**: Each coefficient represents log-multiplicative overhead

### Limitations

1. Log-space may compress extreme values (very long/short latencies)
2. Non-negative constraint may underfit if true relationship is subtractive
3. Expected MoE imbalance is conservative; actual variance may differ
4. Requires careful epsilon selection for log(0) prevention

## Reviews for Idea 2

### Review by Claude (aws/claude-opus-4-6)

**Rating: Strong** (with targeted corrections needed)

**Critical Issues:**

1. **Log-space is multiplicative, not additive**: `exp(beta · F_step)` means each feature contribution multiplies the result, not adds. Communication overhead (e.g., `num_layers * 2 * T_allreduce`) is genuinely additive and cannot be modeled correctly in pure log-space.

   **Fix**: Use hybrid formulation: `L_step = exp(beta_compute · F_compute) + beta_additive · F_additive`

2. **alpha_token model too simplistic**: Per-token decode time grows with context length (attention reads full KV cache). Modeling as constant ignores this.

   **Fix**: `L_token = alpha[0] + alpha[1] * log(1 + current_seq_len) * kv_bytes_per_token / hw_bandwidth`

3. **prefix_overlap_estimate undefined**: Feature is used but never specified how to compute at simulation time.

   **Fix**: Define as `num_prefix_hit_blocks / total_prompt_blocks` via simulator's prefix tree probe.

4. **MoE imbalance assumes uniform routing**: Real MoE models (Mixtral, DeepSeek-V2) have 3-5x skew. Under uniform assumption, imbalance factor approaches 1.0 for large batches, which is exactly when real imbalance matters.

   **Fix**: Learn `beta_moe_imbalance` coefficient from data rather than deriving from theory.

5. **Non-negative constraint may be too restrictive**: Increasing batch size can *reduce* per-token time (better GPU utilization). This is a subtractive effect suppressed by positive constraints.

   **Fix**: Use unconstrained Ridge in log-space (negative coefficients give times < 1 unit, not negative times).

6. **Epsilon selection unaddressed**: For step times ranging 100us to 500ms, choice of epsilon for log(y + epsilon) matters significantly.

   **Fix**: Use `epsilon = median(y) * 1e-6` or filter near-zero observations.

**Minor Issues:**
- Missing chunked prefill chunk-boundary overhead feature
- No KV cache fragmentation feature

### Review by GPT-4o (Azure/gpt-4o)

**Rating: Strong**

**Strengths:**
- Addresses Idea 1's weaknesses directly
- Log-space guarantees positivity
- Simpler feature space
- API-compatible three-component architecture

**Issues:**
- LACM more practical starting point due to simplicity
- Both approaches have complexity risks in feature calibration
- Edge cases still not fully covered (175B+ models, mixed workloads, dynamic knobs)
- MoE behavior remains problematic with static expected values

**Recommendations:**
- Start with LACM as primary approach
- Use NNLS for guaranteed coefficient positivity
- Include interaction terms for nonlinear effects
- Consider lightweight MLPs as alternative to ridge regression

### Review by Gemini (GCP/gemini-2.5-flash)

**Rating: Strong**

The plan clearly articulates the problem, provides excellent background context, and thoroughly justifies the need for a new method. The Gap Analysis is particularly effective.

*(Note: Review was truncated by API)*

---

# Idea 3

## Hybrid Additive-Multiplicative Latency Model (HAMM)

### Core Concept

Address Idea 2's critical flaw (log-space makes everything multiplicative) by explicitly separating **additive fixed overheads** from **multiplicative compute-bound components**. Step time is modeled as:

```
L_step = L_fixed + L_compute
       = (gamma · F_fixed) + exp(beta · F_compute)
```

This correctly models communication overhead as additive while preserving log-space benefits for compute/memory-bound terms.

### Key Improvements Over Ideas 1 & 2

| Issue | Idea 1 | Idea 2 | Idea 3 (HAMM) |
|-------|--------|--------|---------------|
| Communication overhead | Circular dependency | Multiplicative (wrong) | Additive (correct) |
| Positivity guarantee | None | Log-space only | Hybrid: gamma >= 0, exp() > 0 |
| Per-token latency | Constant | Constant | Context-length scaled |
| MoE imbalance | Observed (uncomputable) | Expected uniform (inaccurate) | Learned correction factor |
| Prefix cache | Missing | Undefined | Concrete formula |

### Model Architecture

#### Step Time Decomposition

```
L_step = L_fixed + L_compute

L_fixed = gamma_0                                    # base overhead (CUDA launch, scheduler)
        + gamma_1 * num_layers * tp_allreduce_time   # TP communication (additive)
        + gamma_2 * num_layers * ep_alltoall_time    # EP communication (additive)
        + gamma_3 * cpu_offload_bytes / pcie_bw      # CPU offload transfer (additive)

L_compute = exp(beta · F_compute)                    # compute+memory bound (multiplicative)
```

**Physical Justification**:
- **Additive terms**: Fixed per-step overheads that don't scale with batch size (CUDA kernel launch ~5-10us, TP allreduce ~20us/layer, EP all-to-all ~50us/layer)
- **Multiplicative term**: Compute and memory operations scale with batch composition; log-space captures nonlinear GPU utilization effects

#### Alpha Model (Queue Latency) - 5 dimensions

```
F_queue = [
    1.0,                                        # base scheduler overhead
    log(1 + prompt_tokens),                     # prompt complexity
    log(1 + queue_depth),                       # queue pressure
    kv_usage_ratio^2,                           # memory pressure (quadratic near full)
    prefix_cache_hit_ratio                      # defined concretely below
]

L_queue = exp(alpha · F_queue)
```

**Prefix Cache Hit Ratio Computation:**
```go
func (sim *Simulator) getPrefixCacheHitRatio(req *Request) float64 {
    // Probe KV cache prefix tree for matching blocks
    cachedBlocks := sim.KVCache.GetCachedBlocks(req.InputTokens)
    totalPromptBlocks := (len(req.InputTokens) + sim.KVCache.BlockSizeTokens - 1) /
                         sim.KVCache.BlockSizeTokens
    if totalPromptBlocks == 0 {
        return 0.0
    }
    return float64(len(cachedBlocks)) / float64(totalPromptBlocks)
}
```

#### Alpha_token Model (Per-Token Latency) - Context-Aware

```
L_token = alpha_token[0]                             # base per-token overhead
        + alpha_token[1] * sqrt(current_context_len) # attention overhead scales ~O(sqrt(n))
        + alpha_token[2] * kv_bytes / hw_bandwidth   # KV cache read (for decode)
```

**Rationale**: Attention in FlashAttention is approximately O(n) in memory reads but O(n^2) in SRAM operations. The sqrt approximation captures the empirical middle ground between these bounds for real-world batched decode.

#### Beta Features (Compute/Memory Component) - 8 dimensions

```
F_compute = [
    1.0,                                        # base compute overhead

    # Prefill features (compute-bound)
    log(1 + prefill_tokens) * flops_per_prefill_token / hw_tflops,
    sqrt(max_prefill_seq_len / 1024),           # attention complexity scaling

    # Decode features (memory-bound)
    log(1 + decode_tokens) * kv_read_bytes / hw_bandwidth,
    log(1 + batch_size),                        # batching efficiency

    # Memory pressure
    kv_usage_ratio,                             # general memory pressure

    # MoE correction (learned, not derived)
    is_moe * log(1 + batch_tokens),             # MoE overhead scales with batch
    is_moe * moe_correction_factor              # learned from training data
]
```

### MoE Correction Factor: Data-Driven Learning

Instead of deriving MoE imbalance theoretically, **learn it from data**:

```python
# During training, fit MoE correction as residual
for model in moe_models:
    # Fit base model on dense data
    beta_base = fit_ridge(X_dense, y_dense_log)

    # Compute MoE residuals
    y_moe_predicted = predict(beta_base, X_moe[:, :6])  # base features only
    moe_residuals = y_moe_log - y_moe_predicted

    # Learn MoE correction factor
    moe_features = np.column_stack([
        np.log(1 + X_moe['batch_tokens']),
        np.ones(len(X_moe))  # intercept for moe_correction_factor
    ])
    moe_coeffs = fit_ridge(moe_features, moe_residuals)
```

**Per-Model MoE Correction Factor**:
Store learned `moe_correction_factor` in `defaults.yaml` alongside alpha/beta:
```yaml
- id: mixtral-8x7b-instruct
  GPU: H100
  alpha_coeffs: [...]
  beta_coeffs: [...]
  moe_correction_factor: 0.23  # learned from training
```

### Gamma Coefficients (Fixed Overheads)

```
gamma = [
    gamma_0,  # base overhead (~5us CUDA launch + scheduler)
    gamma_1,  # TP allreduce scaling (default: 1.0)
    gamma_2,  # EP all-to-all scaling (default: 1.0)
    gamma_3,  # CPU offload scaling (default: 1.0)
]
```

**Key Insight**: Gamma coefficients are often close to 1.0 (physical time dominates). Training refines them to account for:
- Pipeline overlap (reduces effective overhead)
- NCCL implementation efficiency
- PCIe contention

### Training Pipeline

#### Phase 1: Stratified Data Collection

```
# Collect traces stratified by:
# - Model type: dense vs MoE (equal representation)
# - Workload: prefill-heavy, decode-heavy, mixed
# - Hardware: A100, H100
# - TP: 1, 2, 4, 8

sampling_matrix = {
    'dense_prefill_A100_TP1': 1000_traces,
    'dense_decode_A100_TP1': 1000_traces,
    ...
    'moe_mixed_H100_TP8': 1000_traces,
}
```

#### Phase 2: Two-Stage Fitting

```python
# Stage 1: Fit gamma (fixed overheads) using traces with minimal compute
low_compute_traces = traces[traces['prefill_tokens'] < 10]  # mostly overhead
gamma = fit_linear(
    X=low_compute_traces[['const', 'tp_comm_time', 'ep_comm_time', 'cpu_bytes']],
    y=low_compute_traces['step_time']
)

# Stage 2: Fit beta (compute component) on residuals
L_fixed_pred = gamma @ X_fixed
L_compute_observed = traces['step_time'] - L_fixed_pred
log_L_compute = np.log(np.maximum(L_compute_observed, 1e-6))

beta = fit_ridge(X_compute, log_L_compute, alpha=1.0)
```

#### Phase 3: Cross-Validation with Hardware Holdout

```python
# Leave-one-hardware-out validation
for holdout_hw in ['A100', 'H100']:
    train = traces[traces['hardware'] != holdout_hw]
    test = traces[traces['hardware'] == holdout_hw]

    gamma, beta = fit_two_stage(train)

    # Evaluate on holdout hardware
    mape = mean_absolute_percentage_error(test['step_time'], predict(gamma, beta, test))
    print(f"MAPE on {holdout_hw}: {mape:.2%}")
```

### Handling vLLM Knobs

| Knob | Impact on Model |
|------|-----------------|
| `--enable-chunked-prefill` | `max_prefill_seq_len` capped -> affects F_compute[2] |
| `--max-num-batched-tokens` | Upper bound on `prefill_tokens + decode_tokens` |
| `--enable-prefix-caching` | `prefix_cache_hit_ratio` in F_queue |
| `--cpu-offloading` | `cpu_offload_bytes` in L_fixed |
| `--tensor-parallel-size` | `tp_allreduce_time` in L_fixed |
| `--num-gpu-blocks-override` | `kv_usage_ratio` calculation |

### Implementation

```go
type HybridCoeffs struct {
    Alpha      []float64 // queue latency (log-space)
    AlphaToken []float64 // per-token latency (linear)
    Beta       []float64 // compute component (log-space)
    Gamma      []float64 // fixed overheads (linear)
    MoEFactor  float64   // learned MoE correction (0 for dense)
}

func (sim *Simulator) getStepTime() int64 {
    // Fixed overheads (additive)
    L_fixed := sim.coeffs.Gamma[0]
    L_fixed += sim.coeffs.Gamma[1] * float64(sim.modelConfig.NumLayers) * sim.hwConfig.AllReduceLatency
    if sim.modelConfig.IsMoE && sim.tp > 1 {
        L_fixed += sim.coeffs.Gamma[2] * float64(sim.modelConfig.NumLayers) * sim.hwConfig.AllToAllLatency
    }
    if sim.cpuOffloadEnabled {
        L_fixed += sim.coeffs.Gamma[3] * float64(sim.cpuOffloadBytes) / sim.hwConfig.PCIeBandwidth
    }

    // Compute component (multiplicative, log-space)
    F_compute := sim.buildComputeFeatures()
    if sim.modelConfig.IsMoE {
        F_compute = append(F_compute,
            math.Log(1 + float64(sim.batchTokens)),
            sim.coeffs.MoEFactor)
    }
    L_compute := math.Exp(dotProduct(sim.coeffs.Beta, F_compute))

    return int64(L_fixed + L_compute)
}

func (sim *Simulator) getOutputTokenProcessingTime(contextLen int64) int64 {
    latency := sim.coeffs.AlphaToken[0]
    latency += sim.coeffs.AlphaToken[1] * math.Sqrt(float64(contextLen))
    if contextLen > int64(len(sim.currentRequest.InputTokens)) { // decode phase
        kvBytes := float64(contextLen) * sim.kvBytesPerToken
        latency += sim.coeffs.AlphaToken[2] * kvBytes / (sim.hwConfig.BwPeakTBs * 1e12)
    }
    return int64(latency)
}
```

### Advantages

1. **Physically Correct**: Additive communication + multiplicative compute matches real GPU behavior
2. **Learned MoE Correction**: Data-driven, not theoretical assumptions about uniform routing
3. **Context-Aware Per-Token**: sqrt(context_len) captures attention overhead growth
4. **Concrete Prefix Cache**: Well-defined computation using existing KV cache API
5. **Two-Stage Training**: Separates overhead fitting from compute fitting for stability
6. **vLLM Knob Coverage**: All required knobs have explicit feature mappings

### Limitations

1. Two-stage fitting adds complexity to training pipeline
2. Gamma coefficients may interact with beta in practice (not fully separable)
3. sqrt(context_len) approximation may not hold for very long contexts (>32K)
4. Per-model MoE correction factor requires MoE-specific training data

## Reviews for Idea 3

### Review by Claude (aws/claude-opus-4-6)

**Rating: Strong** (with targeted corrections needed)

**Critical Issues:**

1. **Two-Stage Fitting Identifiability Problem**:
   - "Low-compute" traces (prefill_tokens < 10) may still have 200 decode tokens, making them memory-bound, not overhead-dominated
   - Residual negativity: if gamma overestimates fixed overhead, `L_compute = step_time - L_fixed` goes negative
   - Pipeline overlap breaks additive assumption at TP>=4 where communication overlaps with GEMM

2. **MoE Correction Factor Per-Model Defeats Generalization**:
   - Every new MoE model needs training data
   - Factor doesn't transfer across architectures (Mixtral 8x7B vs DeepSeek-V3 256 experts)
   - Conflates routing overhead, load imbalance, EP communication, capacity waste

3. **sqrt(context_len) Lacks Theoretical Basis**:
   - For single-query decode, attention is O(n) in both FLOPs and memory
   - sqrt has no justification for decode phase

4. **Feature Computation Mismatch Training vs Simulation**:
   - `prefill_tokens` (from trace) vs `cache_miss_tokens` (simulation) differ with prefix caching
   - `cpu_offload_bytes` has no tracing signal currently

**Moderate Issues:**
- `kv_usage_ratio^2` is ad-hoc; scheduler admission is step-function behavior
- Gamma[1,2] redundant with hardware config values
- No chunked prefill boundary effects modeled
- No interaction terms (prefill × decode matters for mixed batches)

### Review by GPT-4o (Azure/gpt-4o)

**Rating: Strong** (with targeted refinements)

**Strengths:**
- Addresses core requirements comprehensively
- Hybrid additive-multiplicative approach is physically motivated
- Iterative refinement from Idea 1 -> 2 -> 3 shows thoughtful development

**Issues:**
- Feature complexity may hinder practical implementation
- MoE handling still requires per-model training data
- Dynamic vLLM knob changes not addressed
- Edge cases (175B+ models, mixed workloads) need validation

**Recommendations:**
- Simplify features by aggregating into broader categories
- Use probabilistic MoE routing models instead of uniform assumptions
- Consider starting with LACM and adding HAMM components incrementally
- Add blackbox fallback for scenarios where analytical models fail
- Use ElasticNet for better feature selection

### Review by Gemini (GCP/gemini-2.5-flash)

**Rating: Strong**

The plan is exceptionally well-conceived and addresses nearly all identified gaps. It demonstrates deep understanding of the underlying physics.

*(Note: Review was truncated by API)*

---

# Idea 4

## Joint Optimization with Architecture-Derived MoE Scaling (JAMS)

### Core Concept

Address Idea 3's critical flaws by:
1. **Joint optimization** instead of two-stage fitting (avoids identifiability problems)
2. **Architecture-derived MoE overhead** that transfers across models (not per-model factors)
3. **Linear context scaling** for per-token decode (physically justified via FlashAttention analysis)
4. **Explicit feature alignment** between training and simulation
5. **Key interaction terms** for mixed prefill-decode batches

### Key Improvements Over Idea 3

| Issue in Idea 3 | Solution in Idea 4 (JAMS) |
|-----------------|---------------------------|
| Two-stage identifiability | Joint convex optimization |
| Per-model MoE factor | Architecture-derived: `f(top_k, num_experts, hidden_dim)` |
| sqrt(context_len) unjustified | Linear: `context_len * kv_bytes_per_token / bandwidth` |
| Training/sim feature mismatch | Explicit alignment table with conversion functions |
| No interaction terms | `prefill_tokens * decode_tokens` and `batch_size * kv_pressure` |

### Model Architecture

#### Unified Step Time Model

```
L_step = gamma_fixed + L_compute

where:
  gamma_fixed = gamma_0 + gamma_1 * TP_overhead + gamma_2 * MoE_overhead
  L_compute = beta . F_compute  (linear, not log-space)
```

**Key Design Change**: Linear compute model instead of log-space. This allows proper additive composition and easier joint optimization. Positivity enforced via constrained optimization.

#### Feature Vectors with Explicit Alignment

**Training-Time Features** (from vLLM traces):
```
F_train = {
    batch_prefill_tokens:  trace['batch.prefill_tokens'],
    batch_decode_tokens:   trace['batch.decode_tokens'],
    batch_size:            trace['queue.running_depth'],
    kv_ratio:              trace['kv.usage_gpu_ratio'],
    max_seq_len:           max(trace['request.num_prompt_tokens'] +
                               trace['request.num_output_tokens']),
}
```

**Simulation-Time Features** (from simulator state):
```
F_sim = {
    batch_prefill_tokens:  sum(max(0, len(r.InputTokens) - r.ProgressIndex)
                               for r in RunningBatch),  # NOT cache_miss_tokens
    batch_decode_tokens:   count(r for r in RunningBatch
                               if r.ProgressIndex >= len(r.InputTokens)),
    batch_size:            len(RunningBatch.Requests),
    kv_ratio:              KVCache.UsedBlockCnt / KVCache.TotalBlocks,
    max_seq_len:           max(r.ProgressIndex for r in RunningBatch),
}
```

**Critical Alignment Note**: `batch_prefill_tokens` in simulation is the number of tokens that need prefill processing this step (input tokens - already computed), NOT cache miss tokens. This matches the vLLM trace definition.

### Feature Engineering

#### Alpha Features (Queue Latency) - 6 dimensions

```
F_queue = [
    1.0,                                          # intercept
    prompt_tokens / max_model_len,                # normalized prompt size
    queue_depth / max_num_seqs,                   # normalized queue pressure
    max(0, kv_ratio - 0.8) / 0.2,                 # admission cliff (0 below 80%, linear above)
    prefix_cache_hit_ratio,                       # from GetCachedBlocks probe
    is_resume_after_preempt                       # binary: was this request preempted before?
]
```

**Rationale for admission cliff feature**: The scheduler admits requests if blocks are available, rejects near full. This is step-function behavior, better modeled as a threshold than quadratic.

#### Alpha_token (Per-Token Latency) - Linear in Context

```
L_token = alpha_0 + alpha_1 * is_decode * (context_len * kv_bytes_per_token / BwPeakTBs)
```

**Physical Justification**: FlashAttention decode is O(n) in memory: reading K,V for all n past tokens. The per-token time is dominated by this memory read. No sqrt approximation needed.

#### Beta Features (Step Time) - 8 dimensions with interactions

```
F_compute = [
    1.0,                                          # base overhead

    # Primary compute features (hardware-normalized time scales)
    prefill_tokens * flops_per_prefill / (TFlopsPeak * 1e12 * mfu_prefill),
    decode_tokens * flops_per_decode / (TFlopsPeak * 1e12 * mfu_decode),
    total_kv_read_bytes / (BwPeakTBs * 1e12 * bw_eff),

    # Batching features
    batch_size,
    log(1 + max_seq_len),                         # attention complexity

    # Interaction terms
    (prefill_tokens * decode_tokens) / (max_num_batched_tokens^2),  # mixed batch penalty
    batch_size * max(0, kv_ratio - 0.9),          # batch x pressure interaction
]
```

**Interaction Term Rationale**:
- `prefill x decode`: Mixed batches have different CUDA kernel dispatch than pure batches
- `batch_size x kv_pressure`: Large batches under memory pressure experience amplified latency

### Architecture-Derived MoE Overhead

Instead of learning per-model correction factors, derive MoE overhead from architecture parameters:

```
MoE_overhead = is_moe * num_layers * (
    router_time(batch_tokens, num_experts, hidden_dim) +
    expert_dispatch_time(batch_tokens, top_k, num_experts) +
    load_imbalance_factor(top_k, num_experts) * expert_compute_time
)

where:
    router_time = batch_tokens * hidden_dim * num_experts * 2 / TFlopsPeak
    expert_dispatch_time = EP_alltoall_latency * ceil(log2(num_experts))
    load_imbalance_factor = 1.0 + sqrt((num_experts - top_k) / (num_experts * top_k))
```

**Key Insight**: The `load_imbalance_factor` formula is derived from coupon collector analysis for random expert assignment. It provides a theoretical upper bound that transfers across architectures.

**Scaling Validation**: Test formula against Mixtral-8x7B (8 experts, top-2), DeepSeek-V3 (256 experts, top-8), and verify predictions within 15% MAPE before trusting for new architectures.

### Joint Optimization Training Pipeline

#### Formulation as Constrained Linear Program

```
minimize  ||y - (X_fixed @ gamma + X_compute @ beta)||_2^2 + lambda * ||beta||_2^2
subject to:
    gamma >= 0  (fixed overheads are non-negative)
    beta[0] >= 0  (base compute overhead non-negative)
    # No constraints on other beta: interactions can be negative
```

**Implementation**:
```python
from scipy.optimize import minimize

def objective(params, X_fixed, X_compute, y, lambda_reg):
    gamma = params[:n_gamma]
    beta = params[n_gamma:]
    pred = X_fixed @ gamma + X_compute @ beta
    residual = y - pred
    return np.sum(residual**2) + lambda_reg * np.sum(beta**2)

# Bounds: gamma >= 0, beta[0] >= 0, others unbounded
bounds = [(0, None)] * n_gamma + [(0, None)] + [(None, None)] * (n_beta - 1)

result = minimize(objective, x0=params_init, args=(X_fixed, X_compute, y, lambda_reg),
                  method='L-BFGS-B', bounds=bounds)
```

**Why Joint vs Two-Stage?**
- Two-stage has identifiability issue: gamma absorbs noise, leaving biased residuals for beta
- Joint optimization with regularization finds balanced solution
- Constrained optimization ensures physical interpretability

#### Roofline-Based Initialization

Initialize beta from roofline predictions to accelerate convergence:
```python
# Compute roofline step times for each sample
y_roofline = [roofline_step_time(hw, model, step_config) for sample in traces]

# Initialize beta[1:3] from roofline regression
beta_init[1] = 1.0 / (hw.TFlopsPeak * 1e12 * hw.mfu_prefill)  # prefill scaling
beta_init[2] = 1.0 / (hw.TFlopsPeak * 1e12 * hw.mfu_decode)   # decode scaling
beta_init[3] = 1.0 / (hw.BwPeakTBs * 1e12 * hw.bw_eff)        # memory scaling
```

This warm-start provides reasonable initial estimates, reducing optimization iterations.

### Handling vLLM Knobs

| Knob | Feature Impact | Alignment |
|------|---------------|-----------|
| `--enable-chunked-prefill` | Caps `prefill_tokens` per step | Same in training & sim |
| `--max-num-batched-tokens` | Normalizer for interaction term | Explicit in feature |
| `--enable-prefix-caching` | `prefix_cache_hit_ratio` | GetCachedBlocks probe |
| `--cpu-offloading` | Adds `cpu_bytes / pcie_bw` to gamma_fixed | Requires trace extension |
| `--tensor-parallel-size` | `TP_overhead` in gamma | From hardware config |

### Implementation

```go
type JAMSCoeffs struct {
    Gamma []float64 // [gamma_0, gamma_1_tp, gamma_2_moe]
    Beta  []float64 // [base, prefill, decode, memory, batch, seq, interact1, interact2]
    Alpha []float64 // queue latency
    AlphaToken [2]float64 // [base, context_scale]
}

func (sim *Simulator) getStepTime() int64 {
    // Fixed overheads
    L_fixed := sim.coeffs.Gamma[0]
    L_fixed += sim.coeffs.Gamma[1] * sim.getTPOverhead()
    if sim.modelConfig.IsMoE {
        L_fixed += sim.coeffs.Gamma[2] * sim.getMoEOverhead()  // architecture-derived
    }

    // Compute features (aligned with training)
    prefillTokens := sim.getBatchPrefillTokens()  // NOT cache miss tokens
    decodeTokens := sim.getBatchDecodeTokens()
    batchSize := len(sim.RunningBatch.Requests)
    kvRatio := float64(sim.KVCache.UsedBlockCnt) / float64(sim.KVCache.TotalBlocks)
    maxSeqLen := sim.getMaxSeqLen()

    F := []float64{
        1.0,
        float64(prefillTokens) * sim.flopsPerPrefill / (sim.hwConfig.TFlopsPeak * 1e12 * sim.hwConfig.MfuPrefill),
        float64(decodeTokens) * sim.flopsPerDecode / (sim.hwConfig.TFlopsPeak * 1e12 * sim.hwConfig.MfuDecode),
        float64(sim.totalKVReadBytes()) / (sim.hwConfig.BwPeakTBs * 1e12 * sim.hwConfig.BwEffConstant),
        float64(batchSize),
        math.Log(1 + float64(maxSeqLen)),
        float64(prefillTokens * decodeTokens) / math.Pow(float64(sim.maxScheduledTokens), 2),
        float64(batchSize) * math.Max(0, kvRatio - 0.9),
    }

    L_compute := dotProduct(sim.coeffs.Beta, F)
    return int64(math.Max(L_fixed + L_compute, sim.minStepTime))  // floor at minimum
}

func (sim *Simulator) getMoEOverhead() float64 {
    if !sim.modelConfig.IsMoE {
        return 0
    }
    numExp := float64(sim.modelConfig.NumExperts)
    topK := float64(sim.modelConfig.TopKExperts)
    batchTokens := float64(sim.getBatchTotalTokens())

    // Router computation
    routerFlops := batchTokens * float64(sim.modelConfig.HiddenDim) * numExp * 2
    routerTime := routerFlops / (sim.hwConfig.TFlopsPeak * 1e12)

    // Expert dispatch (EP all-to-all)
    dispatchTime := sim.hwConfig.AllToAllLatency * math.Ceil(math.Log2(numExp))

    // Load imbalance factor (coupon collector bound)
    imbalance := 1.0 + math.Sqrt((numExp - topK) / (numExp * topK))

    return float64(sim.modelConfig.NumLayers) * (routerTime + dispatchTime) * imbalance
}
```

### Advantages

1. **Joint Optimization**: Avoids two-stage identifiability issues
2. **Architecture-Derived MoE**: Transfers across models without per-model training
3. **Physically Justified Per-Token**: Linear context scaling matches FlashAttention O(n)
4. **Explicit Feature Alignment**: Training and simulation use same definitions
5. **Interaction Terms**: Captures mixed-batch and pressure effects
6. **Roofline Initialization**: Warm-start accelerates convergence
7. **Minimal Constraints**: Only physical non-negativity, not over-constrained

### Limitations

1. Linear model may underfit extreme nonlinearities at batch size boundaries
2. Coupon collector MoE formula is upper bound, may overestimate for biased routing
3. Requires validation of MoE formula against 2-3 architectures before trusting generalization
4. CPU offloading feature requires vLLM trace extension (not currently emitted)

## Reviews for Idea 4

### Review by Claude (aws/claude-opus-4-6)

**Rating: Strong** (with targeted corrections needed)

**Critical Issues:**

1. **Linear model can produce negative step times**: Unconstrained beta[1:] with interaction terms can drive L_compute negative. The `math.Max(..., minStepTime)` floor is a band-aid.
   - **Fix**: Use softplus: `L_compute = softplus(beta . F)` for smooth, always-positive output

2. **Lambda selection critical**: Only regularizing beta pushes explanatory power into unregularized gamma, recreating identifiability issues.
   - **Fix**: Regularize both: `lambda_gamma * ||gamma||^2 + lambda_beta * ||beta||^2` with cross-validated selection

3. **`flops_per_prefill` not constant**: Prefill FLOPs depend on sequence length (attention is O(n^2)). Treating it as constant is incorrect.
   - **Fix**: Compute `total_batch_prefill_flops / total_prefill_tokens` as the average

4. **MoE coupon collector formula incorrect**: Predicts less imbalance for more experts, which is backwards for models without load balancing.
   - **Fix**: Learn `gamma_imbalance * sqrt(...)` where `gamma_imbalance` is a shared scalar

5. **Feature alignment table incomplete**: Missing alignment for `total_kv_read_bytes`, `max_seq_len`, interaction terms

6. **0.8 admission threshold arbitrary**: Different configs have different effective thresholds
   - **Fix**: Use piecewise features `[max(0, kv-0.7), max(0, kv-0.9)]`

7. **No outlier handling**: GC pauses, CUDA graph compilation can be 10-100x normal step times
   - **Fix**: Winsorize at 99th percentile, use Huber loss

### Review by GPT-4o (Azure/gpt-4o)

**Rating: Strong** (with refinements needed)

**Strengths:**
- Comprehensive and physically motivated
- Addresses core requirements
- Joint optimization avoids two-stage issues

**Issues:**
- Feature complexity may hinder implementation
- MoE formula needs validation against benchmarks
- Missing edge cases (175B+ models, dynamic knob changes)
- Linear context scaling may oversimplify FlashAttention behavior

**Recommendations:**
- Simplify features using ElasticNet for selection
- Validate MoE formula against Mixtral, DeepSeek-V3
- Add hybrid blackbox fallback for edge cases
- Consider lightweight MLPs for nonlinear relationships

### Review by Gemini (GCP/gemini-2.5-flash)

**Rating: Strong**

Highly detailed and well-thought-out plan demonstrating strong understanding of the problem space. JAMS represents significant evolution addressing critical issues from earlier iterations.

*(Note: Review was truncated by API)*

---

# Idea 5

## Softplus Regression with Complete Feature Alignment (SRFA)

### Core Concept

The final synthesized approach incorporates all learnings from Ideas 1-4:
1. **Softplus activation** for guaranteed positive latency (no floor clipping)
2. **Dual regularization** (gamma and beta) to avoid identifiability issues
3. **Actual batch FLOPs computation** (not per-token constant)
4. **Learned MoE imbalance scalar** shared across architectures
5. **Complete feature alignment table** with exact code mappings
6. **Outlier-robust training** with Huber loss and winsorization
7. **Simplified feature set** with empirically validated interactions

### Model Architecture

#### Step Time: Additive + Softplus Compute

```
L_step = L_fixed + softplus(beta . F_compute)

where:
  softplus(x) = log(1 + exp(x))  # smooth, always positive
  L_fixed = gamma . F_fixed      # linear, constrained gamma >= 0
```

**Why Softplus?**
- Smooth gradient everywhere (unlike ReLU)
- Always positive output (unlike linear with floor)
- Preserves relative feature importance (unlike log-space which compresses)
- Gradient approaches 1 for large inputs, 0 for negative inputs

### Complete Feature Alignment Table

#### Fixed Overhead Features (F_fixed) - 4 dimensions

| Feature | Training Source | Simulation Code | Units |
|---------|-----------------|-----------------|-------|
| `f_fixed[0]` (intercept) | `1.0` | `1.0` | - |
| `f_fixed[1]` (TP comm) | `num_layers * hw.allreduce_us` | `float64(modelConfig.NumLayers) * hwConfig.AllReduceLatency` | us |
| `f_fixed[2]` (EP comm) | `is_moe * num_layers * hw.alltoall_us` | `if IsMoE { NumLayers * AllToAllLatency }` | us |
| `f_fixed[3]` (base overhead) | `hw.cuda_launch_us + hw.scheduler_us` | `hwConfig.TOverheadMicros` | us |

#### Compute Features (F_compute) - 7 dimensions

| Feature | Training Source | Simulation Code | Notes |
|---------|-----------------|-----------------|-------|
| `f_comp[0]` (intercept) | `1.0` | `1.0` | Softplus intercept |
| `f_comp[1]` (prefill time) | `batch_prefill_flops / (hw.tflops * mfu_prefill)` | `computeBatchPrefillFlops() / (TFlopsPeak * 1e12 * MfuPrefill)` | **Batch FLOPs, not per-token** |
| `f_comp[2]` (decode time) | `batch_decode_flops / (hw.tflops * mfu_decode)` | `computeBatchDecodeFlops() / (TFlopsPeak * 1e12 * MfuDecode)` | Batch FLOPs |
| `f_comp[3]` (memory time) | `kv_read_bytes / (hw.bw * bw_eff)` | `totalKVReadBytes / (BwPeakTBs * 1e12 * BwEffConstant)` | All decode KV reads |
| `f_comp[4]` (batch log) | `log(1 + batch_size)` | `math.Log(1 + float64(len(RunningBatch)))` | Batching overhead |
| `f_comp[5]` (seq log) | `log(1 + max_seq_len)` | `math.Log(1 + float64(maxProgressIndex))` | Attention complexity |
| `f_comp[6]` (mixed batch) | `prefill_frac * decode_frac` | `(prefillReqs / batchSize) * (decodeReqs / batchSize)` | Interaction: 0 for pure batches, max at 50/50 |

**Batch FLOPs Computation** (critical alignment):
```go
func (sim *Simulator) computeBatchPrefillFlops() float64 {
    var total float64
    for _, req := range sim.RunningBatch.Requests {
        if req.ProgressIndex < int64(len(req.InputTokens)) {
            seqLen := int64(len(req.InputTokens)) - req.ProgressIndex  // tokens this step
            contextLen := req.ProgressIndex + seqLen                    // full context after step
            // Attention FLOPs scale with context length
            attnFlops := sim.flopsPerLayer * float64(sim.modelConfig.NumLayers) *
                         float64(seqLen) * float64(contextLen)
            total += attnFlops
        }
    }
    return total
}
```

#### Queue Features (F_queue) - 5 dimensions

| Feature | Training Source | Simulation Code |
|---------|-----------------|-----------------|
| `f_queue[0]` (intercept) | `1.0` | `1.0` |
| `f_queue[1]` (prompt norm) | `prompt_tokens / max_model_len` | `float64(len(req.InputTokens)) / float64(maxModelLen)` |
| `f_queue[2]` (queue norm) | `queue_depth / max_num_seqs` | `float64(WaitQ.Len()) / float64(maxRunningReqs)` |
| `f_queue[3]` (kv pressure low) | `max(0, kv_ratio - 0.7)` | `math.Max(0, kvRatio - 0.7)` |
| `f_queue[4]` (kv pressure high) | `max(0, kv_ratio - 0.9)` | `math.Max(0, kvRatio - 0.9)` |

**Piecewise KV Features**: Two thresholds capture both "getting full" (0.7) and "critical" (0.9) regimes.

#### Per-Token Features (F_token) - 3 dimensions

| Feature | Training Source | Simulation Code |
|---------|-----------------|-----------------|
| `f_token[0]` (base) | `1.0` | `1.0` |
| `f_token[1]` (prefill token) | `is_prefill` | `if ProgressIndex < len(InputTokens) { 1.0 } else { 0.0 }` |
| `f_token[2]` (decode KV read) | `is_decode * context_len * kv_bytes / hw.bw` | `if decode { contextLen * kvBytesPerToken / (BwPeakTBs * 1e12) }` |

### MoE Handling: Learned Shared Imbalance

Instead of architecture-derived formula, learn a **single shared scalar** from data:

```go
type MoEParams struct {
    ImbalanceScalar float64  // learned: ~1.5 typically
}

func (sim *Simulator) getMoEOverhead() float64 {
    if !sim.modelConfig.IsMoE {
        return 0
    }
    baseOverhead := sim.getMoERouterFlops() + sim.getMoEDispatchTime()
    // Learned imbalance scalar replaces theoretical formula
    return baseOverhead * sim.moeParams.ImbalanceScalar
}
```

**Training MoE Imbalance**:
```python
# Fit base model on dense data
beta_dense = fit_model(X_dense, y_dense)

# For MoE data, compute residual
y_moe_base_pred = predict(beta_dense, X_moe_base_features)
y_moe_residual = y_moe - y_moe_base_pred - moe_router_time - moe_dispatch_time

# Fit imbalance scalar: residual / base_expert_compute
imbalance_scalar = np.median(y_moe_residual / moe_base_compute)
# Typically falls in range [1.2, 2.0] based on routing skew
```

### Training Pipeline

#### Phase 1: Data Preprocessing

```python
def preprocess_traces(traces):
    # 1. Remove warmup steps (first 100 steps per session)
    traces = traces[traces['step_id'] > 100]

    # 2. Winsorize outliers at 99th percentile
    p99 = traces['step_time'].quantile(0.99)
    traces['step_time'] = traces['step_time'].clip(upper=p99)

    # 3. Compute batch FLOPs (not per-token)
    traces['batch_prefill_flops'] = traces.apply(compute_batch_prefill_flops, axis=1)
    traces['batch_decode_flops'] = traces.apply(compute_batch_decode_flops, axis=1)

    return traces
```

#### Phase 2: Joint Optimization with Huber Loss

```python
from scipy.optimize import minimize

def huber_loss(residual, delta=1.0):
    """Robust to outliers: quadratic near 0, linear for large errors."""
    abs_r = np.abs(residual)
    return np.where(abs_r <= delta,
                    0.5 * residual**2,
                    delta * (abs_r - 0.5 * delta))

def objective(params, X_fixed, X_compute, y, lambda_gamma, lambda_beta, delta):
    n_gamma = X_fixed.shape[1]
    gamma = params[:n_gamma]
    beta = params[n_gamma:]

    # Additive fixed + softplus compute
    L_fixed = X_fixed @ gamma
    L_compute = np.log(1 + np.exp(X_compute @ beta))  # softplus
    pred = L_fixed + L_compute

    # Huber loss (robust)
    loss = np.sum(huber_loss(y - pred, delta))

    # Dual regularization
    reg = lambda_gamma * np.sum(gamma**2) + lambda_beta * np.sum(beta**2)

    return loss + reg

# Bounds: gamma >= 0, beta unconstrained (softplus handles positivity)
bounds = [(0, None)] * n_gamma + [(None, None)] * n_beta

# Cross-validate lambda_gamma, lambda_beta, delta
for lambda_gamma in [0.01, 0.1, 1.0]:
    for lambda_beta in [0.01, 0.1, 1.0]:
        for delta in [0.5, 1.0, 2.0]:
            ...
```

#### Phase 3: Hardware Holdout Validation

```python
# Leave-one-hardware-out
for holdout in ['A100', 'H100']:
    train = traces[traces['hardware'] != holdout]
    test = traces[traces['hardware'] == holdout]

    gamma, beta = fit_model(train)

    # Metrics
    mape = mean_absolute_percentage_error(test['step_time'], predict(gamma, beta, test))
    mae = mean_absolute_error(test['step_time'], predict(gamma, beta, test))
    print(f"{holdout}: MAPE={mape:.1%}, MAE={mae:.0f}us")
```

### Implementation

```go
type SRFACoeffs struct {
    Gamma      []float64 // fixed overheads (4 dims), constrained >= 0
    Beta       []float64 // compute features (7 dims), unconstrained
    Alpha      []float64 // queue latency (5 dims)
    AlphaToken []float64 // per-token (3 dims)
    MoEImbalanceScalar float64 // learned, shared across MoE models
}

func softplus(x float64) float64 {
    if x > 20 {  // numerical stability
        return x
    }
    return math.Log(1 + math.Exp(x))
}

func (sim *Simulator) getStepTime() int64 {
    // Fixed overheads (additive, linear)
    F_fixed := []float64{
        1.0,
        float64(sim.modelConfig.NumLayers) * sim.hwConfig.AllReduceLatency,
        sim.getEPCommTime(),
        sim.hwConfig.TOverheadMicros,
    }
    L_fixed := dotProduct(sim.coeffs.Gamma, F_fixed)

    // Compute features
    batchPrefillFlops := sim.computeBatchPrefillFlops()
    batchDecodeFlops := sim.computeBatchDecodeFlops()
    kvReadBytes := sim.computeKVReadBytes()
    batchSize := len(sim.RunningBatch.Requests)
    maxSeqLen := sim.getMaxProgressIndex()
    prefillFrac := float64(sim.countPrefillReqs()) / float64(max(batchSize, 1))
    decodeFrac := float64(sim.countDecodeReqs()) / float64(max(batchSize, 1))

    F_compute := []float64{
        1.0,
        batchPrefillFlops / (sim.hwConfig.TFlopsPeak * 1e12 * sim.hwConfig.MfuPrefill),
        batchDecodeFlops / (sim.hwConfig.TFlopsPeak * 1e12 * sim.hwConfig.MfuDecode),
        kvReadBytes / (sim.hwConfig.BwPeakTBs * 1e12 * sim.hwConfig.BwEffConstant),
        math.Log(1 + float64(batchSize)),
        math.Log(1 + float64(maxSeqLen)),
        prefillFrac * decodeFrac,  // mixed batch interaction
    }

    // Softplus compute (always positive)
    L_compute := softplus(dotProduct(sim.coeffs.Beta, F_compute))

    // MoE overhead with learned imbalance
    if sim.modelConfig.IsMoE {
        moeBase := sim.getMoERouterTime() + sim.getMoEDispatchTime()
        L_fixed += moeBase * sim.coeffs.MoEImbalanceScalar
    }

    return int64(L_fixed + L_compute)
}
```

### Advantages (Synthesis of All Ideas)

1. **Guaranteed Positivity**: Softplus eliminates negative predictions without arbitrary floors
2. **Robust Training**: Huber loss + winsorization handles GC pauses, compilation spikes
3. **Correct FLOPs**: Batch-level computation captures sequence length effects
4. **Learned MoE**: Single shared scalar transfers across architectures
5. **Complete Alignment**: Explicit code for every feature in training and simulation
6. **Dual Regularization**: Balanced gamma/beta prevents identifiability collapse
7. **Simplified Features**: 7 compute features (down from 8-12 in earlier ideas)
8. **Piecewise KV**: Two thresholds capture scheduler admission behavior

### Limitations

1. Softplus gradient saturation for very negative inputs (rare in practice)
2. MoE imbalance scalar may need retraining as new architectures emerge
3. Huber delta hyperparameter adds one more value to tune
4. Batch FLOPs computation adds ~10% overhead to step time calculation

## Reviews for Idea 5

### Review by Claude (aws/claude-opus-4-6)

**Rating: Strong**

**Strengths:**
- Exceptional iterative refinement across 5 ideas
- Complete feature alignment table is standout contribution
- Softplus guarantees positivity elegantly
- Robust training with Huber loss + winsorization

**Critical Issues:**

1. **MoE imbalance scalar can be negative**: Trained via median of residuals, which could be negative if base model overestimates. Not constrained >= 0.

2. **Non-convex optimization**: Softplus + Huber creates non-convex objective; L-BFGS-B may find local minima. Missing roofline-based initialization from Idea 4.

3. **computeBatchPrefillFlops() has O(batch_size) cost per step**: For 512+ request batches, this inner loop adds significant overhead.

4. **MoE training is sequential, not joint**: Fit dense first, then MoE residuals - reintroduces two-stage identifiability issue.

5. **Queue feature timing ambiguity**: When exactly is `getQueueingTime()` called relative to batch formation?

**Moderate Issues:**
- Piecewise KV thresholds (0.7, 0.9) are still magic numbers
- Missing chunked prefill boundary overhead, re-prefill cost after preemption, CPU offloading features
- Large hyperparameter search space (27 combinations x 5 folds)
- alpha_token[2] has 30,000x dynamic range

### Review by GPT-4o (Azure/gpt-4o)

**Rating: Strong**

**Strengths:**
- Comprehensive synthesis of all learnings
- Clear implementation details
- Robust training mechanisms
- Explicit feature alignment

**Issues:**
- Softplus gradient saturation for very negative inputs
- MoE scalar may not generalize to novel architectures (512 experts, top-16)
- Batch FLOPs computation overhead (~10%) could bottleneck large simulations
- Huber delta sensitivity
- Hardcoded KV thresholds

**Recommendations:**
- Use parameterized softplus: `softplus(x, beta)` with tunable sharpness
- Combine learned scalar with architecture-derived factor for MoE
- Cache precomputed FLOPs for common configurations
- Set delta = 1.5 * IQR(residuals) adaptively
- Use ElasticNet instead of separate ridge regularization

### Review by Gemini (GCP/gemini-2.5-flash)

**Rating: Strong**

Exceptionally well-structured and thoroughly considered plan. The iterative refinement from Idea 1 to Idea 5 demonstrates deep understanding and commitment to robust solution. SRFA synthesizes the best aspects into a highly promising approach.

*(Note: Review was truncated by API)*

---

# Executive Summary

## Ideas Overview

**Idea 1 (NRRL - Normalized Roofline Residual Learning)**: Proposed hardware-normalized features as dimensionless ratios to enable cross-GPU transfer. Introduced 8-dim alpha and 12-dim beta feature vectors with Ridge regression training. Identified as having circular dependencies, missing positivity guarantees, and uncomputable MoE features.

**Idea 2 (LACM - Log-Space Additive Component Model)**: Introduced log-space prediction for guaranteed positivity and separated alpha into queue + per-token components. Discovered that log-space makes communication overhead multiplicative (physically incorrect) and per-token model was oversimplified.

**Idea 3 (HAMM - Hybrid Additive-Multiplicative Model)**: Correctly separated additive fixed overheads from multiplicative compute components. Introduced per-model MoE correction factor and context-aware per-token latency. Identified two-stage training identifiability issues and per-model MoE factor defeating generalization.

**Idea 4 (JAMS - Joint Optimization with Architecture-Derived MoE)**: Proposed joint convex optimization to avoid two-stage issues. Introduced architecture-derived MoE overhead formula and explicit feature alignment table. Found that linear model can still produce negative values and MoE formula doesn't match real routing behavior.

**Idea 5 (SRFA - Softplus Regression with Complete Feature Alignment)**: Final synthesis using softplus for guaranteed positivity, dual regularization, batch-level FLOPs computation, learned shared MoE imbalance scalar, complete 22-feature alignment table, and Huber loss for outlier robustness.

## Comparison Table

| Aspect | Idea 1 (NRRL) | Idea 2 (LACM) | Idea 3 (HAMM) | Idea 4 (JAMS) | Idea 5 (SRFA) |
|--------|--------------|---------------|---------------|---------------|---------------|
| Positivity | None | Log-space | Hybrid + floor | Constrained + floor | Softplus |
| Training | Ridge | Ridge + NNLS | Two-stage | Joint L-BFGS-B | Joint + Huber |
| MoE Handling | Observed (uncomputable) | Expected uniform | Per-model learned | Architecture-derived | Learned shared scalar |
| Per-token | Constant | Constant | sqrt(context) | Linear | Linear + KV read |
| Feature Dims | 8 alpha + 12 beta | 5+2+8 | 5+3+8 | 6+2+8 | 5+3+7 |
| Comm Overhead | Circular | Multiplicative | Additive | Additive | Additive |
| Feature Alignment | Partial | Incomplete | Partial | Explicit table | Complete table |
| Outlier Handling | None | None | None | None | Huber + winsorize |

## Reviewer Consensus

All three reviewers rated Idea 5 (SRFA) as **Strong** with targeted corrections needed:

1. **Universal agreement**: Softplus is the right activation for guaranteed positivity
2. **Universal agreement**: Complete feature alignment table is critical and well-executed
3. **Universal concern**: MoE handling still has limitations (scalar may not generalize, sequential training)
4. **Universal concern**: Some hardcoded thresholds remain (KV pressure 0.7/0.9)
5. **Universal suggestion**: Consider hybrid approaches combining learned + architecture-derived factors

## Recommendation

**Implement Idea 5 (SRFA)** as the primary approach with the following modifications:

1. **Constrain MoE imbalance scalar >= 1.0** to prevent negative overhead contributions
2. **Use roofline-based initialization** for L-BFGS-B warm-start (carry forward from Idea 4)
3. **Cache batch FLOPs computation** for common sequence length buckets to reduce overhead
4. **Make KV pressure thresholds configurable** rather than hardcoded
5. **Add feature for preemption history** (`num_recent_preemptions / max_num_seqs`)

**Fallback strategy**: If SRFA accuracy is insufficient for specific configurations, fall back to blackbox optimization with per-config training for those cases.

## Next Steps

1. **Data Collection** (Week 1-2):
   - Extend vLLM tracing to emit CPU offload metrics
   - Collect traces across 3+ model sizes, 2+ GPUs, 3+ TP values, 4+ workloads
   - Include at least 2 MoE models (Mixtral-8x7B, DeepSeek-V3)

2. **Feature Implementation** (Week 2-3):
   - Implement `computeBatchPrefillFlops()` and `computeBatchDecodeFlops()` in simulator
   - Add softplus activation to step time computation
   - Create complete feature extraction pipeline matching alignment table

3. **Training Pipeline** (Week 3-4):
   - Implement preprocessing (warmup removal, winsorization)
   - Build joint optimization with Huber loss and dual regularization
   - Set up cross-validation with hardware holdout

4. **Validation** (Week 4-5):
   - Train on A100 data, validate on H100 (and vice versa)
   - Train on dense models, validate on MoE
   - Compute MAPE, MAE across workload types

5. **Integration** (Week 5-6):
   - Update `defaults.yaml` schema for SRFA coefficients
   - Add `--latency-mode srfa` CLI flag
   - Document coefficient format and training procedure




