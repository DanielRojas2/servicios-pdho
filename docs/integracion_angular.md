# Guía de Integración Frontend: API PDHO en Angular 22

> **Plataforma:** Plataforma Departamental Hotelera de Oruro (PDHO)  
> **Versión de Frontend Objetivo:** Angular 22 (Arquitectura Signals-First, Standalone Components & Zoneless-Ready)  
> **Versión de la API:** v1.0.0 (`/api/v1`)  
> **Estándar de Seguridad:** AGETIC / PISI / ISO 27001 (Bearer Token JWT & RBAC)

---

## 1. Arquitectura y Paradigmas de Angular 22

Esta integración aprovecha los estándares modernos de **Angular 22**:
- **Standalone Components por defecto:** Cero módulos (`NgModule`). Dependencias importadas directamente en `imports: [...]`.
- **Nuevo Control Flow de Templates:** Uso nativo de bloques `@if`, `@for (...; track ...)`, `@empty`, `@switch / @case` y la palabra clave `@let`.
- **Reactividad Nativa con Signals:**
  - `signal<T>()`, `computed<T>()` y `effect()`.
  - Signal-based inputs y outputs: `input()`, `input.required()`, `output()` y enlace bidireccional `model()`.
  - Consultas DOM reactivas con `viewChild()` y `viewChildren()`.
- **Inyección de Dependencias Moderna:** Inyección limpia mediante la función `inject()` eliminando constructores verbosos.
- **Cliente HTTP y Recursos:** `provideHttpClient(withInterceptors([authInterceptor]))` y la API reactiva `httpResource`.

---

## 2. Configuración Global del Entorno

### 2.1 Archivo de Entorno (`src/environments/environment.ts`)

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1',
  appName: 'PDHO - Plataforma Hotelera Oruro',
  tokenStorageKey: 'pdho_access_token',
  userStorageKey: 'pdho_current_user'
};
```

### 2.2 Configuración de la Aplicación (`src/app/app.config.ts`)

```typescript
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding(), withViewTransitions()),
    provideHttpClient(
      withFetch(), // Habilita la API nativa Fetch para máxima velocidad en Angular 22
      withInterceptors([authInterceptor])
    )
  ]
};
```

---

## 3. Contratos de Datos e Interfaces TypeScript (Tipado Estricto)

### 3.1 Modelos de Autenticación y Usuarios (`src/app/core/models/auth.models.ts`)

```typescript
export type RolUsuario = 'ADMIN_DEPARTAMENTAL' | 'OPERADOR_HOSPEDAJE' | 'DEPENDIENTE_HOSPEDAJE';

export interface Usuario {
  id: number;
  email: string;
  nombre_completo: string;
  rol: RolUsuario;
  id_establecimiento: number | null;
  activo: boolean;
  credenciales_enviadas: boolean;
  fecha_creacion: string;
  ultimo_login: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}
```

### 3.2 Modelos de Establecimientos y Capacidad (`src/app/core/models/establecimiento.models.ts`)

```typescript
export type TipoHabitacionNombre = 'simple' | 'doble' | 'matrimonial' | 'triple' | 'multiple' | 'suite';

export interface TipoHabitacionCatalogo {
  id: number;
  tipo_habitacion: TipoHabitacionNombre;
  descripcion: string | null;
}

export interface HabitacionItem {
  id_tipo_habitacion: number;
  tipo_habitacion?: TipoHabitacionNombre;
  cant_habitaciones: number;
  nro_camas: number;
}

export interface Establecimiento {
  id: number;
  nombre_establecimiento: string;
  direccion: string;
  categoria: string;
  latitud: number | null;
  longitud: number | null;
  telefono: string | null;
  total_habitaciones: number; // Suma automática (RN-2)
  total_plazas: number;       // Manual por establecimiento
  id_operador: number | null;
  activo: boolean;
  fecha_registro: string;
  habitaciones: HabitacionItem[];
}

export interface CapacidadHabitacionesUpdate {
  habitaciones: HabitacionItem[];
}
```

### 3.3 Modelos de Nacionalidades (`src/app/core/models/nacionalidad.models.ts`)

```typescript
export interface Nacionalidad {
  id: number;
  pais: string;
  cod_pais: string; // ISO 3166-1 alfa-2 (RN-7) o códigos oficiales (XAM, XEU, etc.)
  continente: string | null;
  activo: boolean;
}

export interface NacionalidadQueryParams {
  skip?: number;
  limit?: number;
  search?: string;
  continente?: string;
  solo_activos?: boolean;
}
```

### 3.4 Modelos de Formularios y Calendario Dinámico (`src/app/core/models/formulario.models.ts`)

```typescript
export type EstadoFormulario = 'BORRADOR' | 'ENVIADO' | 'OBSERVADO' | 'APROBADO';

export interface MesDisponible {
  mes: string;
  numero_mes: number;
  dias_en_mes: number;  // 28, 29 (bisiesto), 30 o 31 días según calendario real
  declarado: boolean;   // true si ya existe en BD para este hotel
  permitido: boolean;   // true si es un mes anterior concluido y no declarado
  formulario_id: number | null;
}

export interface PeriodosDisponiblesResponse {
  gestion: number;
  meses: MesDisponible[];
}

export interface ResumenEstadistica {
  r_ingreso_nals: number;
  r_ingreso_extr: number;
  r_permanencia_nals: number;
  r_permanencia_extr: number;
  total_nals: number;
  total_extr: number;
  total_ing: number;
  total_perm: number;
  total: number;
}

export interface DetalleMovimientoInput {
  dia: number;             // 1 al 31
  id_nacionalidad: number;
  cant_ingresos: number;
  cant_permanencias: number;
}

export interface DetalleMovimientoResponse extends DetalleMovimientoInput {
  id: number;
  pais?: string;
  cod_pais?: string;
}

export interface EstadisticaHoteleraCreate {
  numero_formulario: string; // Número en rojo (ej. "000360")
  mes: string;
  gestion: number;
  fecha_presentacion: string; // Formato YYYY-MM-DD
  cant_emp_perma: number;
  cant_emp_event: number;
  archivo_foto?: string | null;
  archivo_pdf?: string | null;
  detalles: DetalleMovimientoInput[];
  observaciones?: string | null;
  enviar_en_limpio: boolean;
}

export interface OcupacionHoteleraCreate {
  mes: string;
  gestion: number;
  fecha_presentacion: string;
  archivo_foto?: string | null;
  archivo_pdf?: string | null;
  detalles: {
    dia: number;
    hab_ocupadas: number;
    cant_personas: number;
  }[];
  observaciones?: string | null;
  enviar_en_limpio: boolean;
}
```

### 3.5 Modelos de Reportes y Visualización (`src/app/core/models/reportes.models.ts`)

```typescript
export interface PeriodoReporte {
  tipo_filtro: 'rango_fechas' | 'mes_gestion' | 'rango_gestiones' | 'general' | 'gestion_unica';
  descripcion: string;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  mes?: string | null;
  gestion?: number | null;
  gestion_inicio?: number | null;
  gestion_fin?: number | null;
}

export interface SegmentoHuespedes {
  pais?: string | null;
  cod_pais?: string | null;
  cant_ingresos: number;
  cant_permanencias: number;
  total: number;
  porcentaje_ingresos: number;
  porcentaje_permanencias: number;
  porcentaje_total: number;
}

export interface GraficoTortaResponse {
  periodo: PeriodoReporte;
  totales_generales: {
    total_ingresos: number;
    total_permanencias: number;
    total_general: number;
  };
  nacionales: SegmentoHuespedes;
  extranjeros: SegmentoHuespedes;
}

export interface NacionalidadRankingItem {
  ranking: number;
  id_nacionalidad: number;
  pais: string;
  cod_pais: string;
  continente: string | null;
  cant_ingresos: number;
  cant_permanencias: number;
  total_afluencia: number;
  porcentaje_del_total: number;
}

export interface GraficoBarrasRankingResponse {
  periodo: PeriodoReporte;
  total_paises_con_movimiento: number;
  criterio_orden: string;
  top_10: NacionalidadRankingItem[];
  resto: NacionalidadRankingItem[];
  resto_paginacion?: {
    total_items_resto: number;
    skip: number;
    limit: number;
  };
  totales_periodo: {
    total_ingresos: number;
    total_permanencias: number;
    total_general: number;
  };
}

export interface SerieComparativaItem {
  etiqueta: string;
  codigo?: string | null;
  id_nacionalidad?: number | null;
  ingresos: number;
  permanencias: number;
  total: number;
  ratio_permanencia_ingreso: number; // Noches promedio por huésped
}

export interface PermanenciasVsIngresosResponse {
  periodo: PeriodoReporte;
  agrupacion: 'pais' | 'tiempo';
  filtro_paises_aplicado?: string[] | null;
  series: SerieComparativaItem[];
  totales: {
    total_ingresos: number;
    total_permanencias: number;
    promedio_general_noches: number;
  };
}

export interface TableroEjecutivoResponse {
  periodo: PeriodoReporte;
  establecimientos_registrados: number;
  establecimientos_declarantes: number;
  porcentaje_cobertura_establecimientos: number;
  total_formularios_declarados: number;
  total_ingresos: number;
  total_permanencias: number;
  total_huespedes: number;
  total_habitaciones_ofertadas: number;
  total_habitaciones_ocupadas: number;
  tasa_ocupacion_porcentaje: number;
  estadia_media_noches: number;
}
```

---

## 4. Seguridad e Interceptor Funcional en Angular 22

### 4.1 Interceptor HTTP Funcional (`src/app/core/interceptors/auth.interceptor.ts`)

```typescript
import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const token = authService.token();

  // Clonar la solicitud e inyectar el Bearer Token para rutas de la API de PDHO
  let authReq = req;
  if (token && req.url.startsWith(environment.apiUrl)) {
    authReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
  }

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        // Token expirado o manipulado conforme a AGETIC -> Cerrar sesión y redirigir
        authService.logout();
        router.navigate(['/login'], { queryParams: { sesionExpirada: true } });
      } else if (error.status === 403) {
        console.error('Acceso prohibido: permisos insuficientes (RBAC).');
      }
      return throwError(() => error);
    })
  );
};
```

### 4.2 Servicio de Autenticación con Signals (`src/app/core/services/auth.service.ts`)

```typescript
import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { LoginRequest, TokenResponse, Usuario, RolUsuario } from '../models/auth.models';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  // Estados reactivos con Signals
  readonly token = signal<string | null>(localStorage.getItem(environment.tokenStorageKey));
  readonly currentUser = signal<Usuario | null>(this.getStoredUser());

  // Señales calculadas
  readonly isAuthenticated = computed(() => !!this.token() && !!this.currentUser());
  readonly userRole = computed<RolUsuario | null>(() => this.currentUser()?.rol ?? null);
  readonly isAdmin = computed(() => this.userRole() === 'ADMIN_DEPARTAMENTAL');
  readonly isOperador = computed(() => this.userRole() === 'OPERADOR_HOSPEDAJE');

  login(credentials: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiUrl}/usuarios/login`, credentials).pipe(
      tap((res) => {
        localStorage.setItem(environment.tokenStorageKey, res.access_token);
        localStorage.setItem(environment.userStorageKey, JSON.stringify(res.usuario));
        this.token.set(res.access_token);
        this.currentUser.set(res.usuario);
      })
    );
  }

  logout(): void {
    localStorage.removeItem(environment.tokenStorageKey);
    localStorage.removeItem(environment.userStorageKey);
    this.token.set(null);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }

  private getStoredUser(): Usuario | null {
    const raw = localStorage.getItem(environment.userStorageKey);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as Usuario;
    } catch {
      return null;
    }
  }
}
```

### 4.3 Guards Funcionales de Ruta (`src/app/core/guards/auth.guard.ts`)

```typescript
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { RolUsuario } from '../models/auth.models';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/login']);
};

export const roleGuard = (rolesPermitidos: RolUsuario[]): CanActivateFn => {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    const rol = auth.userRole();
    if (rol && rolesPermitidos.includes(rol)) {
      return true;
    }
    return router.createUrlTree(['/dashboard/sin-acceso']);
  };
};
```

---

## 5. Servicios de Dominio Reactivos en Angular 22

### 5.1 Servicio de Formularios y Respaldo Digital (`src/app/core/services/formularios.service.ts`)

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  PeriodosDisponiblesResponse,
  EstadisticaHoteleraCreate,
  OcupacionHoteleraCreate
} from '../models/formulario.models';

@Injectable({
  providedIn: 'root'
})
export class FormulariosService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}`;

  getPeriodosDisponibles(gestion: number, tipo: 'estadistica' | 'ocupacion' = 'estadistica'): Observable<PeriodosDisponiblesResponse> {
    const params = new HttpParams()
      .set('gestion', gestion.toString())
      .set('tipo_formulario', tipo);
    return this.http.get<PeriodosDisponiblesResponse>(`${this.base}/formularios/periodos-disponibles`, { params });
  }

  subirFotoRespaldo(file: File): Observable<{ archivo_foto: string; archivo_pdf: string; mensaje: string }> {
    const formData = new FormData();
    formData.append('archivo', file);
    return this.http.post<{ archivo_foto: string; archivo_pdf: string; mensaje: string }>(
      `${this.base}/formularios/subir-respaldo`,
      formData
    );
  }

  crearEstadisticaHotelera(data: EstadisticaHoteleraCreate): Observable<any> {
    return this.http.post(`${this.base}/estadisticas-hoteleras/`, data);
  }

  crearOcupacionHotelera(data: OcupacionHoteleraCreate): Observable<any> {
    return this.http.post(`${this.base}/ocupacion-hotelera/`, data);
  }
}
```

### 5.2 Servicio de Reportes y Estadísticas (`src/app/core/services/reportes.service.ts`)

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  GraficoTortaResponse,
  GraficoBarrasRankingResponse,
  PermanenciasVsIngresosResponse,
  TableroEjecutivoResponse
} from '../models/reportes.models';

export interface ReporteFiltros {
  fecha_inicio?: string;
  fecha_fin?: string;
  mes?: string;
  gestion?: number;
  gestion_inicio?: number;
  gestion_fin?: number;
  id_establecimiento?: number;
  categoria?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ReportesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/reportes`;

  private buildParams(filtros: ReporteFiltros): HttpParams {
    let params = new HttpParams();
    Object.entries(filtros).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        params = params.set(k, v.toString());
      }
    });
    return params;
  }

  getGraficoNacionalesExtranjeros(filtros: ReporteFiltros): Observable<GraficoTortaResponse> {
    return this.http.get<GraficoTortaResponse>(`${this.base}/graficos/nacionales-extranjeros`, {
      params: this.buildParams(filtros)
    });
  }

  getGraficoRanking(filtros: ReporteFiltros, codigosPais?: string[]): Observable<GraficoBarrasRankingResponse> {
    let params = this.buildParams(filtros);
    if (codigosPais && codigosPais.length > 0) {
      codigosPais.forEach((c) => {
        params = params.append('codigos_pais', c);
      });
    }
    return this.http.get<GraficoBarrasRankingResponse>(`${this.base}/graficos/nacionalidades-ranking`, { params });
  }

  getPermanenciasVsIngresos(filtros: ReporteFiltros, agruparPor: 'pais' | 'tiempo' = 'pais'): Observable<PermanenciasVsIngresosResponse> {
    let params = this.buildParams(filtros).set('agrupar_por', agruparPor);
    return this.http.get<PermanenciasVsIngresosResponse>(`${this.base}/graficos/permanencias-vs-ingresos`, { params });
  }

  getTableroEjecutivo(filtros: ReporteFiltros): Observable<TableroEjecutivoResponse> {
    return this.http.get<TableroEjecutivoResponse>(`${this.base}/tablero-ejecutivo`, {
      params: this.buildParams(filtros)
    });
  }

  descargarReporteCsv(filtros: ReporteFiltros): Observable<Blob> {
    return this.http.get(`${this.base}/exportar/csv`, {
      params: this.buildParams(filtros),
      responseType: 'blob'
    });
  }
}
```

---

## 6. Componentes Funcionales de Ejemplo en Angular 22

### 6.1 Componente Selector de Calendario Dinámico

Implementa la regla de meses habilitados y cálculo de días reales con el nuevo bloque `@for` y Signals.

```typescript
import { Component, ChangeDetectionStrategy, inject, signal, effect, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormulariosService } from '../../core/services/formularios.service';
import { MesDisponible } from '../../core/models/formulario.models';

@Component({
  selector: 'app-calendario-selector',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="calendario-contenedor">
      <div class="gestion-selector">
        <label for="gestion">Gestión:</label>
        <select id="gestion" (change)="onGestionChange($event)">
          <option [value]="2026" selected>2026</option>
          <option [value]="2025">2025</option>
        </select>
      </div>

      <div class="meses-grid">
        @for (m of meses(); track m.numero_mes) {
          @let estaHabilitado = m.permitido && !m.declarado;
          <button 
            type="button" 
            class="mes-card"
            [class.declarado]="m.declarado"
            [class.bloqueado]="!m.permitido && !m.declarado"
            [class.seleccionado]="mesSeleccionado()?.numero_mes === m.numero_mes"
            [disabled]="!estaHabilitado"
            (click)="seleccionarMes(m)">
            <span class="nombre-mes">{{ m.mes }}</span>
            <span class="dias-badge">{{ m.dias_en_mes }} días</span>
            
            @if (m.declarado) {
              <span class="badge declarado-badge">Declarado</span>
            } @else if (!m.permitido) {
              <span class="badge futuro-badge">Bloqueado</span>
            } @else {
              <span class="badge disponible-badge">Disponible</span>
            }
          </button>
        } @empty {
          <p>No se encontraron períodos para la gestión seleccionada.</p>
        }
      </div>
    </div>
  `,
  styles: [`
    .meses-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .mes-card { padding: 14px; border-radius: 8px; border: 1px solid #ccc; cursor: pointer; display: flex; flex-direction: column; align-items: center; }
    .mes-card.seleccionado { border-color: #0d6efd; background-color: #e7f1ff; }
    .mes-card:disabled { opacity: 0.6; cursor: not-allowed; }
  `]
})
export class CalendarioSelectorComponent {
  private readonly formulariosService = inject(FormulariosService);

  readonly gestion = signal<number>(2026);
  readonly meses = signal<MesDisponible[]>([]);
  readonly mesSeleccionado = signal<MesDisponible | null>(null);

  // Output hacia el formulario padre
  readonly onSeleccion = output<MesDisponible>();

  constructor() {
    effect(() => {
      this.cargarPeriodos(this.gestion());
    });
  }

  cargarPeriodos(gestion: number): void {
    this.formulariosService.getPeriodosDisponibles(gestion).subscribe({
      next: (res) => this.meses.set(res.meses),
      error: (err) => console.error('Error al cargar calendario:', err)
    });
  }

  onGestionChange(event: Event): void {
    const val = Number((event.target as HTMLSelectElement).value);
    this.gestion.set(val);
  }

  seleccionarMes(mes: MesDisponible): void {
    this.mesSeleccionado.set(mes);
    this.onSeleccion.emit(mes);
  }
}
```

---

### 6.2 Componente de Subida de Foto y Conversión a PDF

```typescript
import { Component, ChangeDetectionStrategy, inject, signal, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormulariosService } from '../../core/services/formularios.service';

@Component({
  selector: 'app-subir-respaldo-foto',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="carga-respaldo">
      <label class="btn-subir">
        Subir Foto del Formulario Físico
        <input type="file" accept="image/jpeg,image/png" (change)="onFileSelected($event)" style="display: none" />
      </label>

      @if (cargando()) {
        <p class="progreso">Digitalizando imagen y convirtiendo a PDF...</p>
      }

      @if (respaldo(); as r) {
        <div class="resultado-exitoso">
          <p>✅ Respaldo digitalizado con éxito</p>
          <a [href]="r.archivo_pdf" target="_blank" rel="noopener">Ver PDF generado</a>
        </div>
      }
    </div>
  `
})
export class SubirRespaldoFotoComponent {
  private readonly formulariosService = inject(FormulariosService);

  readonly cargando = signal(false);
  readonly respaldo = signal<{ archivo_foto: string; archivo_pdf: string } | null>(null);
  readonly onRespaldoListo = output<{ archivo_foto: string; archivo_pdf: string }>();

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    this.cargando.set(true);

    this.formulariosService.subirFotoRespaldo(file).subscribe({
      next: (res) => {
        this.cargando.set(false);
        const data = { archivo_foto: res.archivo_foto, archivo_pdf: res.archivo_pdf };
        this.respaldo.set(data);
        this.onRespaldoListo.emit(data);
      },
      error: (err) => {
        this.cargando.set(false);
        alert('Error al procesar y convertir la foto a PDF.');
      }
    });
  }
}
```

---

## 7. Mapeo para Librerías de Gráficos (Chart.js / ApexCharts)

### 7.1 Mapeo para Gráfico de Torta (Nacionales vs Extranjeros)

```typescript
// En el componente de Dashboard en Angular 22:
cargarGraficoTorta(res: GraficoTortaResponse) {
  const chartData = {
    labels: ['Nacionales (Bolivia)', 'Extranjeros'],
    datasets: [{
      data: [res.nacionales.total, res.extranjeros.total],
      backgroundColor: ['#28a745', '#007bff'], // Verde y Azul institucional
      hoverOffset: 4
    }]
  };
  return chartData;
}
```

### 7.2 Mapeo para Gráfico de Barras (Top 10 Nacionalidades y Cola)

```typescript
cargarGraficoBarras(res: GraficoBarrasRankingResponse) {
  // Los 10 países con mayor afluencia
  const etiquetas = res.top_10.map(item => `${item.ranking}. ${item.pais}`);
  const llegadas = res.top_10.map(item => item.cant_ingresos);
  const pernoctaciones = res.top_10.map(item => item.cant_permanencias);

  const chartData = {
    labels: etiquetas,
    datasets: [
      { label: 'Llegadas (Ingresos)', data: llegadas, backgroundColor: '#ffc107' },
      { label: 'Pernoctaciones', data: pernoctaciones, backgroundColor: '#17a2b8' }
    ]
  };

  // La lista del 11 en adelante (res.resto) se puede renderizar en una tabla complementaria
  return { chartData, listaCola: res.resto };
}
```

---

## 8. Verificación y Acceso a Swagger / OpenAPI

La API provee la definición de OpenAPI en tiempo real:
- **Swagger UI Interactivo:** `http://localhost:8000/api/v1/docs`
- **ReDoc Documentación:** `http://localhost:8000/api/v1/redoc`
- **JSON OpenAPI Estructurado:** `http://localhost:8000/api/v1/openapi.json`

Se puede generar el cliente completo en Angular automáticamente con:
```bash
npx @openapitools/openapi-generator-cli generate \
  -i http://localhost:8000/api/v1/openapi.json \
  -g typescript-angular \
  -o src/app/api-client
```
