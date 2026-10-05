{{- define "ladedaten.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ladedaten.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else if contains (include "ladedaten.name" .) .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "ladedaten.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "ladedaten.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "ladedaten.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector-Labels; Aufruf mit (dict "ctx" . "component" "app") */}}
{{- define "ladedaten.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ladedaten.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/* Image-Referenz; global.imageRegistry überschreibt die Registry */}}
{{- define "ladedaten.image" -}}
{{- $registry := .global.imageRegistry | default .image.registry -}}
{{- $tag := .image.tag | default .defaultTag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}
{{- end }}

{{- define "ladedaten.appImage" -}}
{{- include "ladedaten.image" (dict "global" .Values.global "image" .Values.image "defaultTag" .Chart.AppVersion) -}}
{{- end }}

{{- define "ladedaten.mariadbImage" -}}
{{- include "ladedaten.image" (dict "global" .Values.global "image" .Values.mariadb.image "defaultTag" "11.4") -}}
{{- end }}

{{- define "ladedaten.mariadbName" -}}
{{- printf "%s-mariadb" (include "ladedaten.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ladedaten.appSecretName" -}}
{{- .Values.auth.existingSecret | default (include "ladedaten.fullname" .) }}
{{- end }}

{{- define "ladedaten.mariadbSecretName" -}}
{{- .Values.mariadb.auth.existingSecret | default (include "ladedaten.mariadbName" .) }}
{{- end }}

{{/*
Wert aus values, sonst aus dem bereits installierten Secret (bleibt bei
Upgrades stabil), sonst neu generiert.
Aufruf: (dict "ctx" . "secret" "<name>" "key" "<key>" "value" <wert>)
*/}}
{{- define "ladedaten.persistentSecret" -}}
{{- if .value -}}
{{- .value -}}
{{- else -}}
{{- $existing := lookup "v1" "Secret" .ctx.Release.Namespace .secret -}}
{{- if and $existing $existing.data (hasKey $existing.data .key) -}}
{{- index $existing.data .key | b64dec -}}
{{- else -}}
{{- randAlphaNum 32 -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/* DB-Umgebungsvariablen für App, Migration und Backup */}}
{{- define "ladedaten.dbEnv" -}}
{{- if eq .Values.database.mode "external" }}
{{- $ext := .Values.database.external }}
{{- $secret := required "database.external.existingSecret ist bei database.mode=external Pflicht" $ext.existingSecret }}
- name: DB_HOST
  valueFrom: {secretKeyRef: {name: {{ $secret }}, key: {{ $ext.hostKey }}}}
- name: DB_PORT
  valueFrom: {secretKeyRef: {name: {{ $secret }}, key: {{ $ext.portKey }}}}
- name: DB_NAME
  valueFrom: {secretKeyRef: {name: {{ $secret }}, key: {{ $ext.databaseKey }}}}
- name: DB_USER
  valueFrom: {secretKeyRef: {name: {{ $secret }}, key: {{ $ext.usernameKey }}}}
- name: DB_PASSWORD
  valueFrom: {secretKeyRef: {name: {{ $secret }}, key: {{ $ext.passwordKey }}}}
{{- else }}
- name: DB_HOST
  value: {{ include "ladedaten.mariadbName" . }}
- name: DB_PORT
  value: "3306"
- name: DB_NAME
  value: {{ .Values.mariadb.auth.database | quote }}
- name: DB_USER
  value: {{ .Values.mariadb.auth.username | quote }}
- name: DB_PASSWORD
  valueFrom: {secretKeyRef: {name: {{ include "ladedaten.mariadbSecretName" . }}, key: mariadb-password}}
{{- end }}
{{- end }}

{{/* Umgebung für Init-Container (Migration) und App */}}
{{- define "ladedaten.appEnv" -}}
- name: SECRET_KEY
  valueFrom: {secretKeyRef: {name: {{ include "ladedaten.appSecretName" . }}, key: secret-key}}
- name: ADMIN_USERNAME
  valueFrom: {secretKeyRef: {name: {{ include "ladedaten.appSecretName" . }}, key: admin-username, optional: true}}
- name: ADMIN_PASSWORD_HASH
  valueFrom: {secretKeyRef: {name: {{ include "ladedaten.appSecretName" . }}, key: admin-password-hash, optional: true}}
{{- include "ladedaten.dbEnv" . }}
{{- with .Values.app.extraEnv }}
{{ toYaml . }}
{{- end }}
{{- end }}
