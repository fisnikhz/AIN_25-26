<table border="0">
 <tr>
    <td><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/University_of_Prishtina_logo.svg/1200px-University_of_Prishtina_logo.svg.png" width="150" alt="University Logo" /></td>
    <td>
      <p>Universiteti i Prishtinës</p>
      <p>Fakulteti i Inxhinierisë Elektrike dhe Kompjuterike</p>
      <p>Inxhinieri Kompjuterike dhe Softuerike - Programi Master</p>
      <p>Profesor: Prof. Dr. Kadri Sylejmani</p>
      <p>Asistent: MSc. Labeat Arbneshi</p>
    </td>
 </tr>
</table>

## Përshkrim

Ky repository është krijuar për lëndën Algoritmet e inspiruara nga natyra për vitin akademik 2025/26. Repository përmban të gjitha zgjidhjet, kodet dhe iterimet e grupeve për secilën javë të lëndës.

## 📋 Detyrat e Implementuara

### Hill Climbing me Random Restarts & Insert Operator
- **File kryesor**: `run_hill_climbing_restarts.py` 
- **Solver**: `solvers/hill_climbing_restarts_solver.py`
- **Insert Operator**: `operators/insert.py`

#### Karakteristika:
- ✅ Random restarts me parametër të konfigurueshëm
- ✅ Insertion operator çdo N iteracione
- ✅ HashMap data structures për performance  
- ✅ Event-based gap detection
- ✅ Comprehensive constraint validation
- ✅ True randomness me timestamp seeds

#### Përdorimi:
```bash
# Direct execution me file argument
python run_hill_climbing_restarts.py data/input/australia_iptv.json

# Interactive file selection  
python run_hill_climbing_restarts.py
```

#### Konfigurimi:
Ndrysho parametrat në `config/config.py`:
```python
NUM_RESTARTS = 10          # Random restarts
INSERTION_INTERVAL = 50    # Insert çdo N iteracione  
MAX_ITERATIONS = 500       # Max iter per restart
```

📖 **Dokumentim i plotë**: Shih `README_DETYRA_E_PLOTE.md`

--- Instruksione për setup dhe workflow në vazhdim të projektit

Hap projektin në editor (VS Code, PyCharm, etj.), pastaj bëni pull nga branch-i kryesor (`main`).

Për çdo javë, secili grup ka një branch të dedikuar me emërtimin java_X, ku X përfaqëson numrin e javës (p.sh., `java_I`, `java_II`, …, `java_XV`).

Bëni merge të ndryshimeve nga branch-i `main` tek branch-i juaj java_X për të marrë versionin më të fundit të kodit.

Nëse keni nevojë për branch të ri, krijoni një branch të ri duke ndjekur formatin: java_X_[placeholder]

Në fund të punës së javës, krijohet një pull request nga branch-i java_X tek branch-i `main`. Pas rishikimit, branch-i i javës bashkohet (merge) me branch-in kryesor (`main`).
