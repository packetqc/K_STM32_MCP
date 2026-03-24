# Methodology — STM32 Firmware Coding

## Purpose

Transform Claude into a disciplined STM32 firmware engineer who writes safe, tested, reusable production code across supported development kits. Every code change follows the SDLC — from requirement analysis through deployment and verification — with full K_MIND memory integration for work tracking and behavioral routing.

---

## Supported Devices

### STM32N6570-DK (Primary)

| Spec | Value |
|------|-------|
| Core | Cortex-M55 (ARMv8.1-M, Helium MVE) |
| RAM | 3.8 MB SRAM (multi-bank AXI) + 128 KB DTCM + 32 MB external PSRAM |
| Flash | Internal flash + 64 MB external NOR (XSPI) |
| Display | 800x480 RGB565 LCD via LTDC |
| Graphics | TouchGFX 4.26.1 + GPU2D (NemaGFX DMA2D) + HW JPEG decoder |
| OS | ThreadX (Azure RTOS) |
| Cache | L1 I-Cache + D-Cache, 32-byte cache line alignment for DMA |
| Security | TrustZone, RIF (Resource Isolation Framework), secure boot via FSBL |
| Boot | FSBL (First Stage BootLoader) → copies app from external flash to SRAM → jump |
| Toolchain | ARM GCC 14.3 (STM32CubeIDE 1.19.0), TouchGFX 4.26.1 asset pipeline |
| Build | `build.bat [all|fsbl|appli|clean]` → `gcc/makefile_fsbl` + `gcc/makefile_appli` |
| Flash | `flash.bat` → STM32CubeProgrammer (sign + program external flash) |

**N6-specific coding rules:**
- DMA buffers MUST be 32-byte aligned (`__attribute__((aligned(32)))`) — Cortex-M55 cache line
- Always invalidate D-Cache before reading DMA rx buffers: `SCB_InvalidateDCache_by_Addr()`
- Always clean D-Cache before DMA tx: `SCB_CleanDCache_by_Addr()`
- PSRAM (0x90000000) is slower than SRAM — use for large assets, not real-time data
- GPU2D operations are async — don't read framebuffer immediately after GPU2D call
- FSBL is a separate build target — changes to boot sequence require rebuilding FSBL
- Linker script `STM32N657XX_LRUN.ld` defines memory regions — respect section placement
- Helium (MVE) SIMD is available — use for DSP/ML workloads via CMSIS-DSP intrinsics
- Security: never expose secure-side data via non-secure callable functions without validation

### STM32H573I-DK (Secondary)

| Spec | Value |
|------|-------|
| Core | Cortex-M33 (ARMv8-M, DSP, FPU) |
| RAM | 640 KB SRAM (contiguous) |
| Flash | 2 MB internal flash |
| Display | 240x240 SPI LCD (ST7789) or external via LTDC (board-dependent) |
| Graphics | TouchGFX (lighter config) or direct framebuffer |
| OS | ThreadX or bare-metal |
| Cache | I-Cache only (no D-Cache — simpler DMA handling) |
| Security | TrustZone, TAMP, HDP, secure boot |
| Crypto | AES, PKA, HASH, RNG, SAES hardware accelerators |
| Connectivity | USB OTG FS, Ethernet, FDCAN, SDMMC, OSPI |
| Toolchain | ARM GCC (STM32CubeIDE), STM32CubeMX for peripheral config |

**H5-specific coding rules:**
- No D-Cache — DMA buffers don't need cache maintenance (simpler than N6)
- 640 KB SRAM total — be aggressive about memory budgets, no room for waste
- 2 MB internal flash — assets must be size-optimized (compress images, reduce fonts)
- No GPU2D — all rendering is software or DMA2D (basic blit, no vector acceleration)
- Crypto accelerators available — use `HAL_CRYP_*` for AES, `HAL_HASH_*` for SHA, don't roll your own
- Ethernet + USB OTG — ideal for connected applications (IoT, industrial)
- FDCAN for automotive/industrial protocols — use HAL FDCAN driver, not raw registers
- Lower clock speed than N6 — optimize hot loops, minimize unnecessary computation
- Smaller stack budgets — 4 KB per thread typical, profile with `uxTaskGetStackHighWaterMark()`

### Cross-Device Portability

When writing code that may run on both platforms:

| Concern | Strategy |
|---------|----------|
| Cache maintenance | Wrap in `#if defined(__DCACHE_PRESENT) && (__DCACHE_PRESENT == 1U)` |
| GPU2D availability | Compile-time check `#ifdef HAL_GPU2D_MODULE_ENABLED` |
| RAM budget | Use `#define` for buffer sizes, set per-device in a config header |
| Display resolution | Abstract via `DISPLAY_WIDTH` / `DISPLAY_HEIGHT` defines |
| Crypto | Use HAL crypto on H5, software fallback on N6 (or vice versa) |
| RTOS | Same ThreadX API on both — portable by default |

---

## Golden Rules

1. **Read before write** — Never modify code you haven't read. Understand the existing state, patterns, and dependencies before touching anything.
2. **One concern per change** — Each modification addresses exactly one feature, fix, or refactor. Never bundle unrelated changes.
3. **Build proves compilation** — Every code change MUST compile before it is considered valid. Run `/flash` or the build step.
4. **Board proves behavior** — Compilation is necessary but not sufficient. Flash and visually/functionally verify on hardware when the device is connected.
5. **No orphan code** — Before writing new code, search the codebase for existing implementations. Reuse > rewrite.
6. **Respect the generated boundary** — Never hand-edit files under `generated/`, `Drivers/`, or `Middlewares/`. These are vendor-managed. User code lives in `gui/src/`, `gui/include/`, `Core/Src/`, `Core/Inc/`.
7. **Track everything** — Every coding task uses K_MIND behavioral routing and memory persistence. No work is invisible.

---

## K_MIND Integration — Work Tracking and Behavioral Routing

### Before Coding Starts

Every coding task MUST follow the K_MIND behavioral routing protocol:

1. **Capture the request** — Save the user's verbatim message to far_memory (`memory_append.py --phase before`)
2. **Route the task** — Run `routing_display.py --callout --subject "<feature>" --action "code"` to identify which methodology and route governs this work
3. **Push onto stack** — `routing_stack.py --push "<route>" --reason "why"` — loads methodology steps
4. **Set WIP context** — `memory_append.py --wip set` with the active branch, work items, and design decisions

### During Coding

- **Mark methodology steps** as you complete them: `routing_stack.py --step "<step>" --note "result"`
- **Log design decisions** to WIP context: `memory_append.py --wip append` — why this approach, what alternatives were rejected
- **Route display** is visible to the user at every turn — compact format for continuation, full callout for new sub-tasks

### After Coding Completes

1. **Save the result** — `memory_append.py --phase after` with full output, summary, tool list
2. **Update mindmap** — Add/modify work nodes in `mind/mind_memory.md` for the completed feature
3. **Update work.json** — Record accomplished work with far_memory references
4. **Pop the route** — `routing_stack.py --pop --status completed` (blocked if methodology steps incomplete)
5. **Commit and push** — Via `/elevate` or manual commit as appropriate

### Why This Matters

- **Compaction recovery** — If context compacts mid-coding, the WIP context and far_memory preserve exactly where you were, what design decisions were made, and what remains
- **Session continuity** — Next session loads near_memory summaries showing the last coding state
- **Audit trail** — Every code change is traceable: user request → route → methodology steps → implementation → commit
- **No invisible work** — The routing display shows the user exactly which rules govern Claude's coding decisions

---

## SDLC Steps (Mandatory Sequence)

### Step 1: Requirement Analysis

**Before writing any code**, answer these questions:

| Question | Purpose |
|----------|---------|
| What exactly should change on the display / in behavior? | Scope the deliverable |
| Which screen/view/presenter is affected? | Identify the modification target |
| Which target device(s)? (N6, H5, or both) | Identify platform constraints |
| Does this need new HAL peripherals (GPIO, I2C, SPI, UART, DMA)? | Identify hardware dependencies |
| Does an existing library/module already do this? | Prevent duplication |
| What is the rollback plan if it breaks? | Safety net |

**Output**: A one-paragraph specification stated to the user before coding begins.

### Step 2: Impact Analysis — Search Before You Write

**MANDATORY: Search the codebase before creating anything new.**

```
Search order:
1. gui/src/ and gui/include/                    — existing view/presenter code
2. Core/Src/ and Core/Inc/                      — HAL init and system code
3. Middlewares/                                  — framework capabilities (TouchGFX, ThreadX)
4. Drivers/                                     — HAL driver availability
5. Knowledge/K_STM32_MCP/libs/                  — reusable project libraries
```

**What to search for:**
- Existing widgets in the `.touchgfx` project file (check `Components` arrays)
- Existing widgets, painters, containers in `gui/` user code
- HAL peripherals already initialized in `main.c` (don't re-init)
- TouchGFX framework classes that solve the problem natively
- Custom libraries in `Knowledge/K_STM32_MCP/libs/` that provide the needed functionality

**Duplication prevention checklist:**
- [ ] Searched `gui/` for similar widget/view patterns
- [ ] Searched `Knowledge/K_STM32_MCP/libs/` for reusable utility code
- [ ] Checked TouchGFX framework headers for native support
- [ ] Checked `main.c` / `stm32n6xx_hal_msp.c` for existing peripheral config

### Step 3: Design — Architecture Before Implementation

**For non-trivial changes (> 20 lines or new module):**

1. **Identify the layer**: GUI (TouchGFX view/presenter) vs System (HAL/driver) vs Library (reusable module)
2. **Choose the pattern**:
   - **TouchGFX GUI**: MVP pattern — View owns widgets, Presenter owns logic, Model owns data
   - **HAL peripheral**: Init in `main.c` MSP callbacks, use via HAL API in application code
   - **Reusable module**: Create in `Knowledge/K_STM32_MCP/libs/<module>/` with `.h` + `.c`, add to Makefile
3. **State the design** to the user in 2-3 sentences before implementing
4. **Log the design decision** to K_MIND WIP context

**Library creation criteria** — Create a reusable library when:
- The same code pattern would be needed in 2+ screens/modules
- The code is self-contained with a clean API (init/deinit/process)
- It wraps a HAL peripheral with project-specific defaults
- It implements a protocol, algorithm, or data structure

**Library structure** (when created):
```
Knowledge/K_STM32_MCP/libs/
  <module_name>/
    <module_name>.h      — Public API (types, function prototypes)
    <module_name>.c      — Implementation
    README.md            — Usage, dependencies, examples (optional)
```

### Step 4: Implementation — Write Production Code

**Code standards:**

| Rule | Rationale |
|------|-----------|
| Follow existing naming conventions in the file | Consistency > preference |
| Use `touchgfx::` namespace explicitly | Clarity in GUI code |
| Use HAL API, never raw register access in application code | Portability, safety |
| Declare canvas buffers `static` at file scope | Lifetime management |
| Initialize widgets fully before `add()` | Prevent partial-render glitches |
| Keep `setupScreen()` focused — helper methods for complex setups | Readability |
| No magic numbers — use named constants or comments | Maintainability |
| Guard all hardware access with HAL status checks | Robustness |

**Safe modification protocol for existing files:**

1. Read the ENTIRE file first (not just the function you're changing)
2. Identify all callers/dependents of what you're modifying
3. Make the minimal change needed
4. Preserve existing formatting, whitespace conventions, include order
5. If adding new includes, place them with similar includes (framework, project, std)
6. **K_MIND tracking**: Log what you changed and why to WIP context — if compaction hits mid-edit, the decision record survives

**Memory safety (critical for embedded):**

- No dynamic allocation (`malloc`/`new`) in application code — use static buffers
- Size all buffers explicitly — document the sizing rationale
- Canvas buffers: minimum 3000 bytes for simple shapes, scale with complexity
- Stack usage: keep view classes lean — large data goes in Model or static storage
- **N6**: DMA buffers must be 32-byte aligned, use cache maintenance before/after DMA
- **H5**: No D-Cache, DMA is simpler — but RAM is tighter (640 KB total)

**ThreadX awareness:**

- GUI runs in the TouchGFX task — never block with infinite waits
- HAL callbacks run in ISR context — defer work to tasks via ThreadX queues/semaphores
- Shared data between tasks needs mutex protection

### Step 5: Build Verification

**Every code change MUST compile successfully.**

```bash
# Build the application
cd gcc && make -f makefile_appli -j8
```

Or use the `/flash` skill which handles the full build pipeline.

**Build failure protocol:**
1. Read the error message carefully — identify the exact file and line
2. Fix the root cause (don't suppress warnings or cast away errors)
3. Rebuild and confirm zero errors, zero new warnings
4. If a warning existed before your change, leave it — don't fix unrelated warnings
5. **Mark step**: `routing_stack.py --step "build-verify" --note "pass/fail"`

### Step 6: Flash and Hardware Verification

**When the device is connected**, flash and verify:

```bash
# Full build + sign + flash pipeline
/flash
```

**Verification checklist:**
- [ ] Device boots without fault (no HardFault, no blank screen)
- [ ] New feature is visually/functionally correct
- [ ] Existing features still work (regression check)
- [ ] No flicker, artifacts, or rendering glitches
- [ ] If using live-session: capture visual proof
- [ ] **Mark step**: `routing_stack.py --step "flash-verify" --note "result"`

### Step 7: Commit, Deliver, and Persist

**Atomic commits with descriptive messages:**

```
<verb> <what> on <where>

<2-3 sentence description of what changed and why>
```

Verbs: `Add`, `Fix`, `Update`, `Remove`, `Refactor`, `Extract` (to library)

**Commit only when:**
- Build passes (Step 5 confirmed)
- Hardware verification passed OR device not connected (noted in commit)
- No debug code left in (no `printf` spam, no hardcoded test values)

**K_MIND persistence (after commit):**
- Update mindmap work nodes with completed feature
- Record in `work/work.json` with far_memory reference
- Pop the routing stack: `routing_stack.py --pop --status completed`
- Push and merge via `/elevate` (default behavior)

---

## Reusable Library Protocol

### Location

All reusable libraries live in `Knowledge/K_STM32_MCP/libs/`. This keeps them with the STM32 knowledge module — portable across projects and devices, versioned with the knowledge system.

### When to Extract

Extract to `Knowledge/K_STM32_MCP/libs/` when you notice:
- Copy-pasting code between screens
- A utility function growing beyond its original view
- A peripheral wrapper that other modules will need
- A data structure or algorithm used in multiple places
- Code that should work on both N6 and H5 targets

### How to Extract

1. **Create** `Knowledge/K_STM32_MCP/libs/<name>/<name>.h` with the public API
2. **Create** `Knowledge/K_STM32_MCP/libs/<name>/<name>.c` with the implementation
3. **Update** `gcc/makefile_appli` — add source to `C_SOURCES` and include path to `C_INCLUDES`
4. **Replace** the original inline code with `#include` + API calls
5. **Build** to verify the extraction didn't break anything
6. **Document** in the library's header: target compatibility (N6, H5, or both), dependencies, usage example

### Library Naming

| Type | Prefix | Example |
|------|--------|---------|
| Display/GUI utilities | `gfx_` | `gfx_shapes`, `gfx_animations` |
| HAL peripheral wrappers | `hw_` | `hw_i2c_sensors`, `hw_uart_debug` |
| Data/algorithm | `util_` | `util_ring_buffer`, `util_pid` |
| Protocol implementations | `proto_` | `proto_modbus`, `proto_canopen` |
| Device-specific | `dev_n6_` / `dev_h5_` | `dev_n6_gpu2d_helper`, `dev_h5_crypto` |

### Library Header Template

```c
/**
 * @file    <module_name>.h
 * @brief   <one-line description>
 * @target  STM32N6570-DK | STM32H573I-DK | Both
 * @deps    <HAL modules required, e.g., HAL_I2C, HAL_DMA>
 */
#ifndef <MODULE_NAME>_H
#define <MODULE_NAME>_H

#include "stm32n6xx_hal.h"  /* or stm32h5xx_hal.h, or conditional */

/* API */
int <module>_init(void);
void <module>_deinit(void);

#endif /* <MODULE_NAME>_H */
```

---

## Forbidden Actions

| Action | Why | Do Instead |
|--------|-----|------------|
| Edit files in `generated/` | Overwritten by TouchGFX Designer | Edit in `gui/src/` user code |
| Edit files in `Drivers/` | Vendor HAL — not project code | Use HAL API, report driver bugs |
| Edit files in `Middlewares/` | Framework code — not yours | Use framework API |
| Use `malloc`/`new` in firmware | Heap fragmentation kills embedded | Static allocation |
| Raw register writes in app code | Bypasses HAL safety | Use `HAL_xxx()` functions |
| Add `#pragma` to suppress warnings | Hides real bugs | Fix the warning |
| Leave `TODO` without a plan | Becomes permanent debt | Fix it or file a work item |
| Modify `main.c` init order blindly | Peripheral dependencies matter | Trace the dependency chain first |
| Copy-paste code between screens | Maintenance nightmare | Extract to `Knowledge/K_STM32_MCP/libs/` |
| Skip K_MIND routing | Work becomes invisible and untrackable | Always route, always persist |
| Code without WIP context | Compaction loses design decisions | Set WIP before implementing |
| Roll your own crypto on H5 | Hardware accelerators exist | Use `HAL_CRYP_*`, `HAL_HASH_*` |
| Ignore cache on N6 | DMA corruption, data races | `SCB_CleanDCache` / `SCB_InvalidateDCache` |

---

## TouchGFX-Specific Patterns

### Adding a Widget to a Screen

```cpp
// In View.hpp — declare as protected member
protected:
    touchgfx::WidgetType myWidget;
    touchgfx::PainterRGB565 myPainter;  // if canvas widget

// In View.cpp — configure in setupScreen() AFTER base call
void MyView::setupScreen()
{
    MyViewBase::setupScreen();  // ALWAYS call base first

    // Configure widget fully before add()
    myWidget.setPosition(x, y, w, h);
    // ... all properties ...
    add(myWidget);
}
```

### Screen Transitions

- Use TouchGFX's built-in transition system (configured in Designer)
- Never manually manage screen lifecycle — let the framework handle it
- Pass data between screens via Model (shared across all presenters)

### Canvas Widgets (Circle, Line, custom shapes)

- **Require** `CanvasWidgetRenderer::setupBuffer()` — call once in `setupScreen()`
- Buffer size: 3000 bytes minimum, increase for complex shapes
- Set `setPrecision()` for curve quality (1 = rough, 10 = smooth, 5 = good default)
- Always set `setArc(0, 360)` for full circles
- **N6 only**: GPU2D can accelerate some canvas operations — check NemaGFX docs

### Performance

- Invalidate only changed regions, not the full screen
- Use `invalidateRect()` for partial updates
- Prefer `PainterRGB565` over `PainterRGB888` (matches display format on both N6 and H5)
- **N6**: GPU2D acceleration is automatic for supported operations — don't fight it
- **H5**: DMA2D basic blit only — optimize software rendering paths

---

## Error Handling in Embedded Context

| Situation | Response |
|-----------|----------|
| HAL function returns `HAL_ERROR` | Log via debug UART, enter safe state, do NOT continue |
| Canvas buffer too small | Increase buffer, document new size rationale |
| Stack overflow | Reduce local variables, move large data to static/global |
| HardFault | Check memory access alignment, NULL pointers, stack overflow |
| Display blank after flash | Verify LTDC init, check FSBL loaded correctly, verify clock config |
| TouchGFX assertion | Read the assertion message — usually a widget not properly initialized |
| DMA corruption (N6) | Check cache maintenance — `Clean` before tx, `Invalidate` before rx |
| Crypto failure (H5) | Check key size, IV setup, HAL_CRYP state machine |

---

## Workflow Summary

```
  [1] REQUIREMENT ─── What exactly needs to change? Which device?
         │
  [2] SEARCH ──────── Does this already exist in libs/? Can I reuse?
         │
  [3] DESIGN ──────── Which layer? Which pattern? Log to WIP.
         │
  [4] IMPLEMENT ───── Minimal, safe, following standards
         │
  [5] BUILD ────────── Zero errors, zero new warnings
         │
  [6] FLASH+VERIFY ── Board proves behavior (when connected)
         │
  [7] COMMIT ──────── Atomic, descriptive, persist to K_MIND
```

**K_MIND wraps the entire cycle:**
- Route display BEFORE step 1 (user sees which rules govern)
- WIP context active from step 3 through step 7
- Methodology steps enforced by routing stack (can't skip)
- Far_memory captures the full audit trail
- Work nodes updated on completion

Each step gates the next. No skipping. No shortcuts. No invisible work.

---

## TouchGFX Application Structure — Coding Convention

### Project Layout (Advanced / STM32CubeMX-Generated)

TouchGFX projects generated via STM32CubeMX use the **advanced** structure. The TGFX application lives under `Appli/TouchGFX/`, not at the project root. This is the layout Claude MUST respect:

```
Appli/TouchGFX/
  gui/                              ◄── USER CODE — Claude codes HERE
    include/gui/
      common/
        FrontendApplication.hpp      — App-level customization
        FrontendHeap.hpp             — Heap configuration
      model/
        Model.hpp                    — Shared data (all presenters see this)
        ModelListener.hpp            — Interface presenters implement
      <screen_name>_screen/
        <Screen>View.hpp             — View: widgets, layout, visual logic
        <Screen>Presenter.hpp        — Presenter: business logic, Model bridge
    src/
      common/
        FrontendApplication.cpp
      model/
        Model.cpp                    — tick(), data updates
      <screen_name>_screen/
        <Screen>View.cpp             — Widget setup, event handlers
        <Screen>Presenter.cpp        — activate/deactivate, Model interaction

  generated/                         ◄── NEVER EDIT — TouchGFX Designer owns this
    gui_generated/
      include/gui_generated/
        <screen_name>_screen/
          <Screen>ViewBase.hpp       — Base class (Designer-managed widgets)
      src/
        <screen_name>_screen/
          <Screen>ViewBase.cpp       — Base setup (Designer-managed)
    fonts/, images/, texts/, videos/ — Asset pipeline output

  target/                            ◄── NEVER EDIT — Board-specific HAL
    TouchGFXHAL.cpp
    STM32TouchController.cpp
```

### MVP Pattern — Mandatory for All Screen Code

TouchGFX enforces **Model-View-Presenter (MVP)**. Claude MUST follow this pattern:

| Component | Role | File Location | Owns |
|-----------|------|---------------|------|
| **View** | Visual layer — widgets, layout, animations | `gui/src/<screen>_screen/<Screen>View.cpp` | Widget instances, visual state |
| **Presenter** | Logic layer — handles events, talks to Model | `gui/src/<screen>_screen/<Screen>Presenter.cpp` | Business logic, Model bridge |
| **Model** | Data layer — shared state, tick-driven updates | `gui/src/model/Model.cpp` | Application data, HAL data bridge |

**Data flow:**
```
  User input → View → Presenter → Model
  Model tick() → Presenter (via ModelListener) → View update
```

**Rules:**
- View NEVER accesses Model directly — always through Presenter
- Presenter NEVER creates or positions widgets — that's View's job
- Model is singleton, shared across all screens — keep it lean
- `ModelListener` interface defines what Presenters can receive from Model

### Widget Creation — Human-Designs, Claude-Codes Convention

**Two distinct coding domains with clear ownership:**

#### Frontend UI Widgets — Human Designs First

Frontend user-facing widgets (buttons, labels, images, layout) are designed by humans in TouchGFX Designer. The Designer generates code into `ViewBase`. Claude MUST:
- **Never edit `ViewBase` or base class files** — Designer regenerates them on every save
- **Never edit the `.touchgfx` project file** to add widgets — humans use the Designer UI for this
- **Use Designer-created widgets** by referencing them in View code (they're inherited from ViewBase)
- **Add runtime behavior** to Designer widgets in View/Presenter (animations, state changes, event handling)

The `.touchgfx` project file (`Appli/TouchGFX/<ProjectName>.touchgfx`) is the Designer's domain. Claude reads it to understand the screen layout but does not modify it for widget creation.

#### Working with Designer-Created Widgets — Claude Codes in the Inherited Class

When humans create widgets in TouchGFX Designer, those widgets are instantiated and owned by `ViewBase` (the base class). Claude programs their behavior in the **inherited View class** — which has full access to all Designer-created widgets via inheritance. Never modify ViewBase to add logic.

```cpp
// Designer created "blueCircle" in ViewBase — Claude uses it in View:
void Screen1View::setupScreen()
{
    Screen1ViewBase::setupScreen();  // base class creates all Designer widgets

    // Claude adds runtime behavior to Designer-created widgets here
    blueCircle.setVisible(sensorActive);  // inherited from ViewBase
}

// Claude adds event handling in View
void Screen1View::handleTickEvent()
{
    // Animate or update Designer widgets at runtime
    blueCircle.setRadius(computedRadius);
    blueCircle.invalidate();
}
```

**The rule:** Designer owns widget creation (ViewBase). Claude owns widget behavior (View). Same widget, two layers, clean separation.

#### Backend / Programmatic Widgets — Claude Codes

For backend logic, programmatic rendering, and dynamic widgets that don't exist at design time, Claude codes directly in View files:

```cpp
// In <Screen>View.hpp — declare as protected member
protected:
    touchgfx::Circle blueCircle;
    touchgfx::PainterRGB565 bluePainter;

// In <Screen>View.cpp — configure in constructor, add in setupScreen()
Screen1View::Screen1View()
{
    bluePainter.setColor(touchgfx::Color::getColorFromRGB(0, 100, 255));

    blueCircle.setPosition(200, 40, 400, 400);
    blueCircle.setCenter(200, 200);
    blueCircle.setRadius(190);
    blueCircle.setLineWidth(0);
    blueCircle.setArc(0, 360);
    blueCircle.setPainter(bluePainter);
    blueCircle.setPrecision(5);
}

void Screen1View::setupScreen()
{
    Screen1ViewBase::setupScreen();  // ALWAYS call base first
    add(blueCircle);
}
```

**Claude codes in View files when:**
- Implementing backend-driven visuals (sensor data display, status indicators)
- Creating programmatic/dynamic widgets computed at runtime
- Adding behavior and logic to Designer-created widgets
- Working in Presenter and Model layers (always code, never Designer)

#### Never Touch Base Classes

| File | Who Owns It | Claude Can Edit? |
|------|-------------|-----------------|
| `<Screen>View.hpp / .cpp` | Developer (Claude + human) | **YES** |
| `<Screen>Presenter.hpp / .cpp` | Developer (Claude + human) | **YES** |
| `Model.hpp / .cpp` | Developer (Claude + human) | **YES** |
| `<Screen>ViewBase.hpp / .cpp` | TouchGFX Designer | **NEVER** |
| `<ProjectName>.touchgfx` | TouchGFX Designer (human) | **NEVER** for widget creation |

### Interaction Handling — Presenter Takes the Logic

When widgets need interaction (buttons, touch events, callbacks):

```cpp
// View catches the UI event, delegates to Presenter
void Screen1View::onButtonClicked()
{
    presenter->handleButtonAction();  // View → Presenter
}

// Presenter processes logic, may update Model
void Screen1Presenter::handleButtonAction()
{
    // Business logic here
    model->setSomeState(true);        // Presenter → Model
}

// Model notifies all Presenters via ModelListener
void Model::tick()
{
    if (stateChanged) {
        modelListener->stateUpdated(value);  // Model → Presenter
    }
}

// Presenter updates View
void Screen1Presenter::stateUpdated(int value)
{
    getView()->refreshDisplay(value);  // Presenter → View
}
```

### Editable vs Read-Only Boundaries

| Path | Editable? | Who Owns It |
|------|-----------|-------------|
| `gui/src/` and `gui/include/` | **YES** | Developer (Claude) |
| `generated/gui_generated/` | **NO** | TouchGFX Designer — regenerated on save |
| `generated/fonts/`, `images/`, `texts/` | **NO** | Asset pipeline — regenerated on build |
| `target/` | **NO** | Board HAL — configured via CubeMX/Designer |
| `Core/Src/`, `Core/Inc/` | **YES** (carefully) | System init — CubeMX generates, user sections editable |

### Custom Containers (Future)

Custom containers follow the same MVP structure but are reusable across screens. They will have their own View/Presenter pairs under `gui/src/containers/`. Convention details will be added when this pattern is needed.

### Key Takeaways

1. **Humans design frontend UI** — widgets created in TouchGFX Designer, generated into ViewBase
2. **Claude codes backend logic** — programmatic widgets, behavior, Presenter/Model in View files
3. **Never touch base classes** — ViewBase and `.touchgfx` are Designer's domain
4. **Code in `gui/` only** — View/Presenter/Model user code
5. **Logic in Presenter** — never put business logic in View
6. **Data in Model** — shared state lives here, driven by `tick()`
7. **MVP is not optional** — it's how TouchGFX works, not a style preference
