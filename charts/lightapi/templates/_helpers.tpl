{{- define "lightapi.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "lightapi.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lightapi.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lightapi.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "lightapi.labels" -}}
helm.sh/chart: {{ include "lightapi.chart" . }}
{{ include "lightapi.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "lightapi.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lightapi.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lightapi.databaseSecretName" -}}
{{- default (include "lightapi.fullname" .) .Values.database.existingSecret -}}
{{- end -}}

{{- define "lightapi.jwtSecretName" -}}
{{- default (include "lightapi.fullname" .) .Values.jwt.existingSecret -}}
{{- end -}}
