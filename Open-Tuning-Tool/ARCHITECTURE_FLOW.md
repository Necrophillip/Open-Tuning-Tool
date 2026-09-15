# Open Tuning Tool - Architecture & Workflow

Este documento describe la arquitectura completa del motor inteligente (Necro Engine), el flujo de trabajo de la aplicación, y la base matemática detrás de las recomendaciones de tuning.

## Arquitectura del Sistema

```mermaid
flowchart TD
    subgraph UI ["Capa de Presentación (PyQt6)"]
        Wizard[Wizard Shell]
        Extraction[Extracción CLI/BBL]
        Review[Tuning Page (Review)]
        Export[Export Page (CLI)]
    end

    subgraph Core ["Motor Heurístico (Necro Engine)"]
        Context[Tuning Context Guard]
        Advisor[PID Tuning Advisor]
        
        subgraph Analyzers ["Analizadores de Telemetría"]
            PID[Step Response PID]
            EZLanding[TPA / EZ-Landing]
            Notch[Dynamic Notch]
            RPM[RPM Filter]
            DTerm[D-Term Filter]
            Gyro[Gyro Filter]
        end
    end

    subgraph Analysis ["Capa de Procesamiento Matemático"]
        Loader[Blackbox Loader]
        StepMath[Step Response Math]
        LandingMath[Landing Bounce Math]
    end

    subgraph Hardware ["Controlador de Vuelo"]
        FC[Flight Controller]
    end

    %% Relaciones
    FC -->|CLI Dump & Status| Extraction
    FC -->|Blackbox Logs| Loader
    Extraction --> Context
    Loader --> StepMath
    Loader --> LandingMath
    
    Context --> Advisor
    StepMath --> PID
    LandingMath --> EZLanding
    
    Advisor --> DTerm
    Advisor --> Gyro
    Advisor --> RPM
    RPM -->|Inyección de Dependencia| Notch
    Advisor --> PID
    Advisor --> EZLanding
    
    Advisor -->|PIDTuningRecommendation| Review
    Review --> Export
    Export -->|CLI Commands| FC
```

## Flujo de Trabajo (Workflow)

1. **Extracción**: La aplicación se conecta al puerto serie del Flight Controller. Ejecuta los comandos `dump` y `status`. Se parsea la versión de Betaflight, los parámetros actuales, y el modelo del giroscopio.
2. **Carga de Log (Blackbox)**: Se utiliza `blackbox_decode` para convertir el archivo `.bbl` en un DataFrame de pandas.
3. **Generación de Contexto (Safety Gate)**: `version_gyro_guard.py` evalúa la firma del firmware y el giroscopio. Si detecta anomalías (ej. versión no soportada, log de autotune/chirp), emite **Blocking Flags** (como `gyro_unknown_conservative_mode`) que previenen modificaciones peligrosas.
4. **Análisis Matemático**:
   - `compute_step_response_summary`: Aísla flips/rolls rápidos. Ajusta una curva ideal de 1er y 2do orden a la respuesta del giroscopio frente al comando RC.
   - `measure_landing_bounce`: Busca caídas de acelerador a cero y mide la varianza (RMS) resultante en el giroscopio para detectar rebotes al aterrizar.
5. **Evaluación de Reglas (Analyzers)**:
   - **RPM Filter**: Evalúa el nivel global de ruido y activa hasta 3 armónicos. Retorna su cobertura.
   - **Dynamic Notch**: Lee la cobertura del RPM. Si hay ruido residual en bandas medias/bajas, ajusta `count`, `Q`, y `min_hz` sin solapar con RPM.
   - **Step Response PID**: Compara el amortiguamiento real con el modelo críticamente amortiguado.
   - **EZ-Landing**: Usa el rebote medido para aplicar una tasa (rate) directamente proporcional, calculando el punto de inicio (breakpoint) basado en el acelerador de vuelo real.
6. **Revisión y Exportación**: El motor compila todo en un bloque de comandos CLI, permitiendo al usuario revisar el razonamiento detrás de cada cambio antes de flashear el dron.

## Tecnología Matemática (Física de Control)

El proyecto abandona las reglas "mágicas" y hardcodeadas a favor de teoría de control clásica aplicada a telemetría real.

### 1. Modelo de Segundo Orden y Factor de Amortiguamiento ($\zeta$)
El analizador PID extrae la **Sobreoscilación (Overshoot %)** del log y la invierte matemáticamente para encontrar el factor de amortiguamiento ($\zeta$ o *damping ratio*) de un sistema de segundo orden ideal:

$$ \zeta = \frac{\ln\left(\frac{100}{OS\%}\right)}{\sqrt{\pi^2 + \ln\left(\frac{100}{OS\%}\right)^2}} $$

- **Objetivo**: Sistema críticamente amortiguado ($\zeta \approx 1$).
- **Corrección**: Si $\zeta < 0.456$ (Muy subamortiguado), el sistema restará ganancia Proporcional (P) y aumentará Derivativa (D) para frenar la oscilación.
- **Responsividad**: Un eje independiente evalúa el *Rise Time* (tiempo de subida). Si el dron es lento (>150ms), se inyecta más P.
- *Nota: Si tu dron ya tiene $\zeta > 0.69$ y un Rise Time veloz, el motor considerará que está óptimamente tuneado y **no sugerirá cambios PID**. Un buen afinador silencioso es mejor que uno que daña un quad ya funcional.*

### 2. Filtros Dinámicos Basados en RMS
El ruido no se asume, se mide. Se calcula la Raíz Cuadrada Media (RMS) del vector giroscópico a lo largo del vuelo. 
- Filtro RPM y Notch coordinan mediante inyección de dependencias. Si el ruido RMS es de 141.2°/s (alto), RPM absorbe los 3 primeros armónicos del motor. 
- Para evitar retraso de fase (phase delay), Notch lee que RPM ya cubrió esa banda y se reduce a `count=1` para limpiar solo las frecuencias de resonancia del frame, actuando como un bisturí en lugar de un mazo.

### 3. TPA / EZ-Landing Interpolado
En lugar de fijar valores estáticos para todos los quads, la aplicación busca el evento físico del aterrizaje (throttle cut + impacto) y mide la amplitud máxima de la perturbación (Bounce RMS). 
El `tpa_low_rate` se calcula usando un multiplicador definido en las reglas y un límite de seguridad. El `tpa_low_breakpoint` se ancla dinámicamente un 10% por debajo del punto de vuelo estacionario (*hover*) del piloto, garantizando que el suavizado sólo aplique a centímetros del suelo y jamás durante acrobacias.
