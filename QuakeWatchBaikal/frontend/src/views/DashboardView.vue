<template>
  <div style="display: flex; width: 100vw; height: 100vh">
    <SidebarControls />
    <SeismicMap />
    <PolarizationModal />
  </div>
</template>

<script setup lang="ts">
import SidebarControls from '@/components/SidebarControls.vue';
import SeismicMap from '@/components/SeismicMap.vue';
import PolarizationModal from '@/components/PolarizationModal.vue';
</script>
