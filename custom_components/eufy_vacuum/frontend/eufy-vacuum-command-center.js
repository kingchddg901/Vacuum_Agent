var De="eufy-vacuum-command-center";var _="eufy_vacuum";var Ze="clear_queue";var et="get_start_status",tt="start_selected_rooms";var rt="get_pause_timeout_settings",at="set_pause_timeout_settings",it="get_room_profiles",nt="save_user_room_profile",ct="save_room_profile_from_room",st="overwrite_room_profile",ot="overwrite_room_profile_from_room",lt="rename_room_profile",dt="delete_room_profile",ut="apply_room_profile",mt="update_room_fields",vt="get_saved_run_profiles",pt="save_run_profile",ht="overwrite_run_profile",ft="apply_run_profile",gt="rename_run_profile",_t="delete_run_profile";var bt="get_theme_library",yt="save_theme_as_new",xt="overwrite_theme",wt="rename_theme",St="delete_theme",Rt="set_active_theme",Et="update_working_draft",kt="revert_draft",Tt="export_theme",$t="import_theme",Mt="upload_map_image",It="analyze_map_image",At="get_map_segments",Ct="adjust_map_segment",Lt="set_segment_room_link",Pt="set_companion_anchor",Ot="setup_get_status",Nt="setup_add_vacuum",Ft="setup_import_active_map",Ht="setup_get_map_rooms",Dt="setup_save_rooms",Bt="setup_delete_map";function Z(i){let e=String(i||"").split(".");return e.length>1?e[1]:e[0]}var ve={dockEvents:i=>`sensor.${Z(i)}_dock_events`,themeState:i=>`sensor.${Z(i)}_theme_state`,profileSensor:i=>`sensor.${Z(i)}_available_profiles`,activeMap:i=>`sensor.${Z(i)}_active_map`,robotPositionXRaw:i=>`sensor.${Z(i)}_robot_position_x_raw`,robotPositionYRaw:i=>`sensor.${Z(i)}_robot_position_y_raw`},Ee=new Set(["unknown","unavailable",""]);function jt(i){i.entity=function(e){return e?this.hass?.states?.[e]??null:null},i.stateOf=function(e){return this.entity(e)?.state??null},i.attrsOf=function(e){return this.entity(e)?.attributes??{}},i.isValidState=function(e){return e==null?!1:!Ee.has(String(e))},i.hasEntity=function(e){let t=this.stateOf(e);return t!==null&&this.isValidState(t)},i.vacuumEntityId=function(){return this.config?.vacuum_entity_id??null},i.vacuumObjectId=function(){return Z(this.vacuumEntityId())},i.vacuumState=function(){let e=this.vacuumEntityId();return e?this.stateOf(e):null},i.vacuumAttrs=function(){let e=this.vacuumEntityId();return e?this.attrsOf(e):{}},i.batteryLevel=function(){let e=this.vacuumAttrs()?.battery_level,t=Number(e);return Number.isFinite(t)?t:null},i.vacuumDisplayName=function(){let e=this.vacuumAttrs();if(e?.friendly_name)return String(e.friendly_name).trim();let t=this.vacuumObjectId();return t?t.replace(/_/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Vacuum"},i.rawRobotPosition=function(){let e=this.vacuumEntityId();if(!e)return null;let t=Number(this.stateOf(ve.robotPositionXRaw(e))),r=Number(this.stateOf(ve.robotPositionYRaw(e)));return!Number.isFinite(t)||!Number.isFinite(r)?null:{x:Math.round(t),y:Math.round(r)}},i.attrOf=function(e,t,r=null){let n=this.attrsOf(e)?.[t];return n!==void 0?n:r}}function zt(i){i._ensureDockState=function(){return this._dockState||(this._dockState={actionStatus:null,pendingAction:"",pauseTimeoutSettings:null}),this._dockState},i.setDockActionStatus=function(e){this._ensureDockState().actionStatus=e??null},i.dockActionStatus=function(){return this._ensureDockState().actionStatus??null},i.beginDockAction=function(e){this._ensureDockState().pendingAction=String(e??"")},i.endDockAction=function(){this._ensureDockState().pendingAction=""},i.pendingDockAction=function(){return this._ensureDockState().pendingAction??""},i.isDockActionPending=function(e){return this.pendingDockAction()===String(e??"")},i.dockActionGate=function(e){return this.dockActionStatus()?.actions?.[e]??null},i.dockActionAllowed=function(e){return this.dockActionGate(e)?.allowed===!0},i.dockStatus=function(){return this.dockActionStatus()?.dock_status??this.dashboardUpkeep?.()?.dock_status??null},i.dockStatusLabel=function(){return this.dockActionStatus()?.dock_status_label??this.dashboardUpkeep?.()?.dock_status_label??null},i.dockLifecycleState=function(){return this.dockActionStatus()?.lifecycle_state??null},i.dockLifecycleStateLabel=function(){return this.dockActionStatus()?.lifecycle_state_label??null},i.dockTaskStatus=function(){return this.dockActionStatus()?.task_status??this.dockActionStatus()?.active_job_status??null},i.dockTaskStatusLabel=function(){return this.dockActionStatus()?.task_status_label??this.dockActionStatus()?.active_job_status_label??null},i.isDocked=function(){return this.dockActionStatus()?.docked===!0},i.stationWaterLabel=function(){return this.dashboardUpkeep?.()?.station_water_label??null},i.setPauseTimeoutSettings=function(e){this._ensureDockState().pauseTimeoutSettings=e??null},i.pauseTimeoutSettings=function(){return this._ensureDockState().pauseTimeoutSettings??null},i.pauseTimeoutMinutesDefault=function(){let e=this.pauseTimeoutSettings?.(),t=Number(e?.pause_timeout_minutes_default);return Number.isFinite(t)?t:null}}var de={LEARNING:"learning",ROOMS:"rooms",PROFILES:"profiles",WATER:"water",DOCK:"dock",BATTERY:"battery"};function Vt(i){i._ensureMetricsState=function(){return this._metricsState||(this._metricsState={snapshot:null,filters:{room_slug:"",profile_key:"",status:"",used_for_learning:""},activeTab:de.LEARNING,pendingSaveKey:""}),this._metricsState},i.metricsSnapshot=function(){return this._ensureMetricsState().snapshot??null},i.setMetricsSnapshot=function(e){let t=this._ensureMetricsState();t.snapshot=e??null;let r=e?.filters;r&&typeof r=="object"&&(t.filters={room_slug:r.room_slug==null?"":String(r.room_slug),profile_key:r.profile_key==null?"":String(r.profile_key),status:r.status==null?"":String(r.status),used_for_learning:typeof r.used_for_learning=="boolean"?String(r.used_for_learning):""})},i.metricsFilters=function(){return this._ensureMetricsState().filters},i.setMetricsFilter=function(e,t){let r=this.metricsFilters();e in r&&(r[e]=t==null?"":String(t))},i.metricsActiveTab=function(){return this._ensureMetricsState().activeTab??de.LEARNING},i.setMetricsActiveTab=function(e){let t=String(e??"").trim().toLowerCase();Object.values(de).includes(t)&&(this._ensureMetricsState().activeTab=t)},i.metricsTabOptions=function(){return[{value:de.LEARNING,label:"Learning"},{value:de.ROOMS,label:"Rooms"},{value:de.PROFILES,label:"Profiles"},{value:de.WATER,label:"Water"},{value:de.DOCK,label:"Dock"},{value:de.BATTERY,label:"Battery"}]},i.metricsOverview=function(){return this.metricsSnapshot()?.overview??{}},i.metricsSelection=function(){return this.metricsSnapshot()?.selection??{}},i.metricsRooms=function(){return Array.isArray(this.metricsSnapshot()?.rooms)?this.metricsSnapshot().rooms:[]},i.metricsRoomProfiles=function(){return Array.isArray(this.metricsSnapshot()?.room_profiles)?this.metricsSnapshot().room_profiles:[]},i.metricsFoundProfiles=function(){return Array.isArray(this.metricsSnapshot()?.found_profiles)?this.metricsSnapshot().found_profiles:[]},i.metricsLearningStats=function(){return this.metricsSnapshot()?.room_learning_stats??{}},i.metricsSources=function(){return this.metricsSnapshot()?.sources??{}},i.beginMetricsProfileSave=function(e){this._ensureMetricsState().pendingSaveKey=String(e??"")},i.endMetricsProfileSave=function(){this._ensureMetricsState().pendingSaveKey=""},i.isMetricsProfileSavePending=function(e){return this._ensureMetricsState().pendingSaveKey===String(e??"")},i.metricsProfileSaveKey=function(e,t){let r=String(e??"profile"),a=String(t?.room_slug??""),n=String(t?.profile_key??"");return`${r}:${a}:${n}`},i.findMetricsSaveCandidate=function(e,t,r=""){let a=String(e??""),n=String(t??""),c=String(r??"");return n?(a==="found"?this.metricsFoundProfiles?.()??[]:this.metricsRoomProfiles?.()??[]).find(o=>String(o?.profile_key??"")===n&&String(o?.room_slug??"")===c)??null:null},i.metricsFilterRoomOptions=function(){let e=this.metricsSnapshot()?.filter_options?.rooms;return Array.isArray(e)&&e.length?e:[]},i.metricsFilterProfileOptions=function(){let e=this.metricsSnapshot()?.filter_options?.profiles;return Array.isArray(e)&&e.length?e:[]},i.metricsFilterStatusOptions=function(){let e=this.metricsSnapshot()?.filter_options?.statuses;return Array.isArray(e)&&e.length?e:[]},i.metricsFilterUsedOptions=function(){let e=this.metricsSnapshot()?.filter_options?.used_for_learning;return Array.isArray(e)&&e.length?e:[]},i._batterySensor=function(e){let t=this.vacuumObjectId();if(!t)return null;let r=`sensor.${t}_${e}`,a=this.stateOf(r);return a==null?null:{entity_id:r,state:a,attrs:this.attrsOf(r)??{}}},i.batteryMetrics=function(){return{cycles:this._batterySensor("charge_cycles"),health:this._batterySensor("battery_health"),rate_overall:this._batterySensor("charge_rate"),rate_low:this._batterySensor("charge_rate_low_zone"),rate_high:this._batterySensor("charge_rate_high_zone"),rate_mid_job:this._batterySensor("mid_job_recharge_rate"),last_charge_duration:this._batterySensor("last_charge_duration"),last_job_per_min:this._batterySensor("last_job_drain_rate")||this._batterySensor("last_job_drain_per_min"),last_job_per_hour:this._batterySensor("last_job_drain_per_hour"),last_job_per_m2:this._batterySensor("last_job_drain_per_m2")||this._batterySensor("last_job_drain_per_m_")}}}function qt(i){i._ensureOrderState=function(){return this._orderState||(this._orderState={scope:null,activeItemId:null,targetPosition:null,dragItemId:null,dragOverItemId:null}),this._orderState},i.resetOrderState=function(){this._orderState={scope:null,activeItemId:null,targetPosition:null,dragItemId:null,dragOverItemId:null}},i._normalizeNumericOrder=function(e,t=999999){let r=Number(e);return Number.isFinite(r)?r:t},i._sortOrderedItems=function(e,t){let r=Array.isArray(e)?[...e]:[],a=t.getOrder,n=t.getId;return r.sort((c,s)=>{let o=this._normalizeNumericOrder(a(c)),l=this._normalizeNumericOrder(a(s));if(o!==l)return o-l;let d=String(n(c)),u=String(n(s));return d.localeCompare(u)})},i._reindexOrderedItems=function(e,t){let r=t.setOrder;return e.map((a,n)=>r(a,n+1))},i._moveOrderedItemToPosition=function(e,t,r,a){let n=this._reindexOrderedItems(this._sortOrderedItems(e,t),t),c=t.getId,s=Math.max(1,Math.min(Number(a)||1,n.length)),o=n.findIndex(u=>String(c(u))===String(r));if(o===-1)return n;let l=[...n],[d]=l.splice(o,1);return l.splice(s-1,0,d),this._reindexOrderedItems(l,t)},i._swapOrderedItemsById=function(e,t,r,a){let n=this._reindexOrderedItems(this._sortOrderedItems(e,t),t),c=t.getId,s=n.findIndex(u=>String(c(u))===String(r)),o=n.findIndex(u=>String(c(u))===String(a));if(s===-1||o===-1||s===o)return n;let l=[...n],[d]=l.splice(s,1);return l.splice(o,0,d),this._reindexOrderedItems(l,t)},i._buildOrderPatch=function(e,t){let r=t.getId,a=t.getOrder;return e.map(n=>({id:r(n),order:this._normalizeNumericOrder(a(n),1)}))},i.getOrderAdapter=function(e){return null},i.getOrderedItemsForScope=function(e){let t=this.getOrderAdapter(e);if(!t?.getItems)return[];let r=t.getItems.call(this);return this._reindexOrderedItems(this._sortOrderedItems(r,t),t)},i.getOrderedItemById=function(e,t){let r=this.getOrderedItemsForScope(e),a=this.getOrderAdapter(e);return a?r.find(n=>String(a.getId(n))===String(t))??null:null},i.getOrderedItemPosition=function(e,t){let r=this.getOrderedItemsForScope(e),a=this.getOrderAdapter(e);if(!a)return null;let n=r.findIndex(c=>String(a.getId(c))===String(t));return n===-1?null:n+1},i.openOrderSelector=function(e,t){let r=this._ensureOrderState(),a=this.getOrderedItemPosition(e,t);r.scope=e,r.activeItemId=t,r.targetPosition=a},i.closeOrderSelector=function(){let e=this._ensureOrderState();e.scope=null,e.activeItemId=null,e.targetPosition=null},i.isOrderSelectorOpen=function(){let e=this._ensureOrderState();return!!(e.scope&&e.activeItemId!=null)},i.orderSelectorScope=function(){return this._ensureOrderState().scope},i.orderSelectorItemId=function(){return this._ensureOrderState().activeItemId},i.orderSelectorItem=function(){let e=this._ensureOrderState();return!e.scope||e.activeItemId==null?null:this.getOrderedItemById(e.scope,e.activeItemId)},i.orderSelectorTargetPosition=function(){return this._ensureOrderState().targetPosition},i.setOrderSelectorTargetPosition=function(e){let t=this._ensureOrderState();t.targetPosition=Number(e)||1},i.orderSelectorPositions=function(){let e=this._ensureOrderState();if(!e.scope)return[];let t=this.getOrderedItemsForScope(e.scope);return Array.from({length:t.length},(r,a)=>a+1)},i.beginOrderDrag=function(e,t){let r=this._ensureOrderState();r.scope=e,r.dragItemId=t,r.dragOverItemId=t},i.setOrderDragOverItem=function(e){let t=this._ensureOrderState();t.dragOverItemId=e},i.orderDragItemId=function(){return this._ensureOrderState().dragItemId},i.orderDragOverItemId=function(){return this._ensureOrderState().dragOverItemId},i.clearOrderDrag=function(){let e=this._ensureOrderState();e.dragItemId=null,e.dragOverItemId=null},i.previewMovedItemsForScope=function(e,t,r){let a=this.getOrderAdapter(e);if(!a)return[];let n=a.getItems.call(this);return this._moveOrderedItemToPosition(n,a,t,r)},i.previewDraggedItemsForScope=function(e,t,r){let a=this.getOrderAdapter(e);if(!a)return[];let n=a.getItems.call(this);return this._swapOrderedItemsById(n,a,t,r)}}function Gt(i){i._ensureRoomProfilesState=function(){return this._roomProfilesState||(this._roomProfilesState={profile_count:0,protected_profile_names:[],profiles:{}}),this._roomProfilesState},i._normalizeRoomProfile=function(e,t={}){return{name:String(e??""),label:String(t?.label??e??"Unnamed Profile"),clean_mode:String(t?.clean_mode??"vacuum"),fan_speed:String(t?.fan_speed??""),water_level:String(t?.water_level??""),clean_intensity:String(t?.clean_intensity??"Quick"),clean_passes:Number(t?.clean_passes??1),carpet:!!t?.carpet,edge_mopping:!!t?.edge_mopping}},i.setRoomProfilesLibrary=function(e){let t=this._ensureRoomProfilesState(),r=e?.profiles&&typeof e.profiles=="object"&&!Array.isArray(e.profiles)?e.profiles:{},a=Array.isArray(e?.protected_profile_names)?e.protected_profile_names.map(n=>String(n)):[];t.profile_count=Number(e?.profile_count??Object.keys(r).length??0),t.protected_profile_names=a,t.profiles=Object.fromEntries(Object.entries(r).map(([n,c])=>[String(n),this._normalizeRoomProfile(n,c)]).filter(([n])=>n))},i.roomProfilesLibrary=function(){return this._ensureRoomProfilesState().profiles},i.roomProfilesCount=function(){return this._ensureRoomProfilesState().profile_count??0},i.protectedRoomProfileNames=function(){return this._ensureRoomProfilesState().protected_profile_names??[]},i.isProtectedRoomProfile=function(e){let t=String(e??"").trim();return t?this.protectedRoomProfileNames().includes(t):!1},i.roomProfileDefinition=function(e){let t=String(e??"").trim();return t?this.roomProfilesLibrary()?.[t]??null:null},i.roomProfilesList=function(){let e=this.roomProfilesLibrary();return Object.values(e).sort((t,r)=>{let a=this.isProtectedRoomProfile(t.name),n=this.isProtectedRoomProfile(r.name);return a!==n?a?-1:1:String(t.label).localeCompare(String(r.label),void 0,{sensitivity:"base"})})},i.customRoomProfiles=function(){return this.roomProfilesList().filter(e=>!this.isProtectedRoomProfile(e.name))},i.makeRoomProfileName=function(e,t=null){let a=String(e??"").trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"").replace(/_+/g,"_"),n=a?`custom_${a}`:"custom_profile",c=String(t??"").trim();if(c&&c===n)return c;let s=new Set(Object.keys(this.roomProfilesLibrary()??{}));if(!s.has(n))return n;let o=2;for(;s.has(`${n}_${o}`);)o+=1;return`${n}_${o}`}}function Ut(i){i._emptyRunProfileDraft=function(){return{name:"",expose_as_button:!1}},i._normalizeRunProfilesPayload=function(e){return Array.isArray(e)?{profiles:e,library:{}}:e&&typeof e=="object"?{profiles:Array.isArray(e.profiles)?e.profiles:Array.isArray(e.saved_run_profiles)?e.saved_run_profiles:[],library:e.library&&typeof e.library=="object"&&!Array.isArray(e.library)?e.library:{}}:{profiles:[],library:{}}},i._normalizeRunProfile=function(e){return{id:String(e?.id??e?.profile_id??""),name:String(e?.name??"Unnamed Profile"),vacuum_entity_id:String(e?.vacuum_entity_id??""),map_id:String(e?.map_id??""),room_count:Number(e?.room_count??0),room_ids:Array.isArray(e?.room_ids)?e.room_ids:[],room_names:Array.isArray(e?.room_names)?e.room_names:[],room_names_label:String(e?.room_names_label??""),expose_as_button:!!e?.expose_as_button,summary:String(e?.summary??""),created_at:String(e?.created_at??""),updated_at:String(e?.updated_at??""),rooms:Array.isArray(e?.rooms)?e.rooms:[]}},i._ensureRunProfilesState=function(){return this._runProfilesState||(this._runProfilesState={profiles:[],selectedProfileId:null,editorOpen:!1,editorMode:"new",editorProfileId:null,draft:this._emptyRunProfileDraft()}),this._runProfilesState},i.setRunProfilesLibrary=function(e){let t=this._ensureRunProfilesState(),r=this._normalizeRunProfilesPayload(e),a=r.profiles.map(n=>{let c=String(n?.id??n?.profile_id??""),s=c&&r.library?.[c]?r.library[c]:null;return this._normalizeRunProfile({...n,...s??{}})}).filter(n=>n.id);t.profiles=a,t.selectedProfileId&&!a.some(n=>n.id===t.selectedProfileId)&&(t.selectedProfileId=null),t.editorProfileId&&!a.some(n=>n.id===t.editorProfileId)&&(t.editorOpen=!1,t.editorMode="new",t.editorProfileId=null,t.draft=this._emptyRunProfileDraft())},i.savedRunProfiles=function(){return this._ensureRunProfilesState().profiles},i.savedRunProfilesCount=function(){return this.savedRunProfiles().length},i.selectedRunProfileId=function(){return this._ensureRunProfilesState().selectedProfileId??null},i.selectedRunProfile=function(){let e=this._ensureRunProfilesState();return e.profiles.find(t=>t.id===e.selectedProfileId)??null},i.selectRunProfile=function(e){let t=this._ensureRunProfilesState();t.selectedProfileId=e?String(e):null},i.openNewRunProfileEditor=function(){let e=this._ensureRunProfilesState();e.editorOpen=!0,e.editorMode="new",e.editorProfileId=null,e.draft=this._emptyRunProfileDraft()},i.openSelectedRunProfileEditor=function(){let e=this._ensureRunProfilesState(),t=this.selectedRunProfile();t&&(e.editorOpen=!0,e.editorMode="edit",e.editorProfileId=t.id,e.draft={name:t.name,expose_as_button:!!t.expose_as_button})},i.closeRunProfileEditor=function(){let e=this._ensureRunProfilesState();e.editorOpen=!1,e.editorMode="new",e.editorProfileId=null,e.draft=this._emptyRunProfileDraft()},i.isRunProfileEditorOpen=function(){return this._ensureRunProfilesState().editorOpen===!0},i.runProfileEditorMode=function(){return this._ensureRunProfilesState().editorMode??"new"},i.runProfileDraft=function(){return this._ensureRunProfilesState().draft},i.updateRunProfileDraft=function(e,t){let r=this._ensureRunProfilesState();if(e==="expose_as_button"){r.draft={...r.draft,expose_as_button:!!t};return}r.draft={...r.draft,[e]:t}}}var pe={NEWEST:"newest",OUTLIER:"outlier",SUGGESTED:"suggested",EXCLUDED:"excluded"},Wt="manual_test_run",Jt=Object.freeze({clean_mode:"Vacuum",fan_speed:"Standard",water_level:null,clean_intensity:"Quick",clean_passes:1,edge_mopping:!1});function Kt(i){i._ensureReviewState=function(){return this._reviewState||(this._reviewState={snapshot:null,filters:{room_slug:"",profile_key:"",status:"",used_for_learning:"",limit:50},sort:pe.NEWEST,excludeReasons:{},pendingJobActionId:"",matcherFields:{...Jt}}),this._reviewState},i.learningHistorySnapshot=function(){return this._ensureReviewState().snapshot??null},i.setLearningHistorySnapshot=function(e){let t=this._ensureReviewState();t.snapshot=e??null;let r=e?.filters;r&&typeof r=="object"&&(t.filters={room_slug:r.room_slug==null?"":String(r.room_slug),profile_key:r.profile_key==null?"":String(r.profile_key),status:r.status==null?"":String(r.status),used_for_learning:typeof r.used_for_learning=="boolean"?String(r.used_for_learning):"",limit:Number.isFinite(Number(r.limit))&&Number(r.limit)>0?Number(r.limit):t.filters?.limit??50})},i.learningHistoryFilters=function(){return this._ensureReviewState().filters},i.setLearningHistoryFilter=function(e,t){let r=this.learningHistoryFilters();if(e in r){if(e==="limit"){let a=Number(t);r[e]=Number.isFinite(a)&&a>0?a:50;return}r[e]=t==null?"":String(t)}},i.learningHistorySort=function(){return this._ensureReviewState().sort??pe.NEWEST},i.setLearningHistorySort=function(e){let t=String(e??"").trim().toLowerCase();Object.values(pe).includes(t)&&(this._ensureReviewState().sort=t)},i.learningHistoryJobs=function(){let e=this.learningHistorySnapshot()?.jobs;return Array.isArray(e)?e:[]},i.learningHistoryRooms=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.rooms;if(Array.isArray(e)&&e.length)return e.filter(c=>String(c?.value??"").trim()!=="").map(c=>({room_slug:String(c?.value??""),room_name:String(c?.label??c?.value??"")}));let t=this.learningHistorySnapshot?.(),r=Array.isArray(t?.rooms)?t.rooms:[],a=Array.isArray(t?.jobs)?t.jobs.flatMap(c=>Array.isArray(c?.room_slugs)?c.room_slugs.map(s=>({room_slug:s,room_name:this._formatReviewRoomLabel?.(s)??s})):[]):[],n=new Map;for(let c of[...r,...a]){let s=String(c?.room_slug??c?.slug??"").trim();s&&(n.has(s)||n.set(s,{room_slug:s,room_name:c?.room_name??c?.label??this._formatReviewRoomLabel?.(s)??s}))}return Array.from(n.values()).sort((c,s)=>String(c.room_name??c.room_slug).localeCompare(String(s.room_name??s.room_slug)))},i.learningHistoryProfiles=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.profiles;if(Array.isArray(e)&&e.length)return e.filter(c=>String(c?.value??"").trim()!=="").map(c=>({profile_key:String(c?.value??""),label:String(c?.label??c?.value??""),subtitle:c?.subtitle==null?null:String(c.subtitle),room_slug:c?.room_slug==null?null:String(c.room_slug),room_label:c?.room_label==null?null:String(c.room_label)}));let t=this.learningHistorySnapshot?.(),r=Array.isArray(t?.found_profiles)?t.found_profiles:[],a=Array.isArray(t?.room_profiles)?t.room_profiles:[],n=new Map;for(let c of[...r,...a]){let s=String(c?.profile_key??"").trim();s&&(n.has(s)||n.set(s,{profile_key:s,label:c?.profile_label??c?.label??c?.selected_profile_label??s,subtitle:c?.profile_subtitle??c?.resolved_profile_label??null}))}return Array.from(n.values()).sort((c,s)=>String(c.label??c.profile_key).localeCompare(String(s.label??s.profile_key)))},i.learningHistoryExcludeReason=function(e){return this._ensureReviewState().excludeReasons[String(e??"")]||Wt},i.setLearningHistoryExcludeReason=function(e,t){this._ensureReviewState().excludeReasons[String(e??"")]=String(t??Wt)},i.beginLearningHistoryJobAction=function(e){this._ensureReviewState().pendingJobActionId=String(e??"")},i.endLearningHistoryJobAction=function(){this._ensureReviewState().pendingJobActionId=""},i.isLearningHistoryJobActionPending=function(e){return this._ensureReviewState().pendingJobActionId===String(e??"")},i.learningHistorySortOptions=function(){return[{value:pe.NEWEST,label:"Newest"},{value:pe.OUTLIER,label:"Highest Outlier"},{value:pe.SUGGESTED,label:"Suggested Exclude"},{value:pe.EXCLUDED,label:"Excluded Only"}]},i.learningHistoryStatusOptions=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.statuses;return Array.isArray(e)&&e.length?e.map(t=>({value:String(t?.value??""),label:String(t?.label??t?.value??"")})):[{value:"",label:"All Statuses"},{value:"completed",label:"Completed"},{value:"canceled",label:"Canceled"},{value:"failed",label:"Failed"},{value:"interrupted",label:"Interrupted"}]},i.learningHistoryUsedOptions=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.used_for_learning;return Array.isArray(e)&&e.length?e.map(t=>({value:String(t?.value_key??t?.value??""),label:String(t?.label??t?.value_key??t?.value??"")})):[{value:"",label:"All Learning Use"},{value:"true",label:"Used For Learning"},{value:"false",label:"Not Used For Learning"}]},i.learningHistoryExcludeReasonOptions=function(){return[{value:"short_test_cancel",label:"Short Test Cancel"},{value:"manual_test_run",label:"Manual Test Run"},{value:"false_completion",label:"False Completion"},{value:"bad_room_attribution",label:"Bad Room Attribution"},{value:"interrupted_run",label:"Interrupted Run"}]},i._formatReviewRoomLabel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())},i.reviewProfileMatcherFields=function(){return this._ensureReviewState().matcherFields},i.resetReviewProfileMatcher=function(){this._ensureReviewState().matcherFields={...Jt}},i.setReviewProfileMatcherField=function(e,t){let r=this.reviewProfileMatcherFields();if(!r||!(e in r))return;let a=t;if(e==="clean_mode"&&(a=this._canonicalCleanModeDisplay?.(t)??t),e==="clean_passes"){let n=Number(t);a=Number.isFinite(n)&&n>0?n:1}e==="edge_mopping"&&(a=t===!0||String(t??"").trim().toLowerCase()==="true"),r[e]=a,e==="clean_mode"&&!this.isMopMode?.(a)&&(r.water_level=null,r.edge_mopping=!1)},i.showReviewProfileMatcherWaterLevel=function(){let e=this.reviewProfileMatcherFields();return e?this.isMopMode?.(e.clean_mode)??!1:!1},i.showReviewProfileMatcherEdgeMopping=function(){let e=this.reviewProfileMatcherFields();return e?this.isMopMode?.(e.clean_mode)??!1:!1},i.reviewProfileMatcherCatalog=function(){let e=this.attrsOf?.(ve.profileSensor(this.vacuumEntityId()))??{},t=e.profiles??{},r=e.profile_labels??{},a=this.learningHistoryProfiles?.()??[],n=new Map(a.map(s=>[String(s?.profile_key??""),String(s?.label??s?.profile_key??"")]).filter(([s])=>s)),c=new Map;for(let[s,o]of Object.entries(t)){let l=String(s??"").trim();l&&(c.has(l)||c.set(l,{profile_key:l,label:n.get(l)||r[l]||l,definition:o}))}for(let s of a){let o=String(s?.profile_key??"").trim();!o||c.has(o)||c.set(o,{profile_key:o,label:String(s?.label??o),definition:null})}return Array.from(c.values()).sort((s,o)=>String(s.label??s.profile_key).localeCompare(String(o.label??o.profile_key)))},i.reviewProfileMatcherMatches=function(){let e=this.reviewProfileMatcherFields(),t=this.reviewProfileMatcherCatalog();return!e||!t.length?[]:t.filter(r=>r?.definition?this._editorFieldsMatchProfile?.(e,r.definition)===!0:!1)}}function Yt(i){i._normalizeRoomReferenceList=function(e){return e==null?[]:(Array.isArray(e)?e:[e]).map(r=>String(r??"").trim()).filter(r=>r!=="")},i._buildRoomAccessAdjacency=function(e=[]){let t={};return e.forEach(r=>{t[String(r.id)]=this._normalizeRoomReferenceList(r.grantsAccessTo)}),t},i._roomAccessGraphHasCycle=function(e={}){let t=new Set,r=new Set,a=n=>{if(r.has(n))return!0;if(t.has(n))return!1;t.add(n),r.add(n);let c=e[n]??[];for(let s of c)if(s in e&&a(s))return!0;return r.delete(n),!1};return Object.keys(e).some(n=>a(n))},i.roomAccessGraph=function(e=null){let t=e==null?this.getRoomsForActiveMap():this.getRoomsForMap(e),r=this._buildRoomAccessAdjacency(t);return t.map(a=>{let n=String(a.id),c=r[n]??[],s=t.filter(o=>(r[String(o.id)]??[]).includes(n)).map(o=>String(o.id));return{roomId:n,grantsAccessTo:c,requiresAccessFrom:s}})},i.validateRoomAccessUpdate=function(e,t,r=[]){let a=this.getRoomsForMap(e),n=String(t??"").trim(),c=new Set(a.map(h=>String(h.id))),s=this._normalizeRoomReferenceList(r),o=s.filter((h,y)=>s.indexOf(h)!==y),l=Array.from(new Set(s)),d=l.filter(h=>!c.has(h)),u=l.includes(n),v=[];c.has(n)||v.push({code:"missing_room",message:"This room no longer exists on the active map."}),u&&v.push({code:"self_reference",message:"A room cannot grant access to itself."}),o.length&&v.push({code:"duplicate_edges",message:"Each access link can only appear once.",roomIds:Array.from(new Set(o))}),d.length&&v.push({code:"missing_room_references",message:"All access links must point to rooms on the current map.",roomIds:d});let m=this._buildRoomAccessAdjacency(a),p=this._buildClaimedTargetMap(a,n),f=l.filter(h=>p.has(h)&&c.has(h));if(f.length){let h=Object.fromEntries(a.map(y=>[String(y.id),y.name]));f.forEach(y=>{let x=p.get(y),w=h[x]??`Room ${x}`,g=h[y]??`Room ${y}`;v.push({code:"multiple_inbound",message:`${g} already has an inbound link from ${w}. Each room can only be reached from one room.`,roomIds:[y,x].filter(Boolean)})})}return m[n]=l.filter(h=>c.has(h)),!v.length&&this._roomAccessGraphHasCycle(m)&&v.push({code:"cycle",message:"This access setup would create a loop in the room graph."}),{valid:v.length===0,issues:v,normalizedGrantsAccessTo:m[n]??[]}},i.orphanedRooms=function(e=null){let t=e!=null?this.getRoomsForMap(e):this.getRoomsForActiveMap();if(!t.some(n=>n.isDockRoom))return[];let a=new Set;return t.forEach(n=>{this._normalizeRoomReferenceList(n.grantsAccessTo).forEach(c=>{a.add(c)})}),t.filter(n=>n.isDockRoom?!1:!a.has(String(n.id)))},i._buildClaimedTargetMap=function(e=[],t=""){let r=new Map;return e.forEach(a=>{String(a.id)!==String(t)&&this._normalizeRoomReferenceList(a.grantsAccessTo).forEach(n=>{r.has(n)||r.set(n,String(a.id))})}),r},i.setStartStatus=function(e){this._startStatus=e??null},i.startPreflight=function(){let e=this.dashboardJobControl?.()?.preflight??this.dashboardStartStatus?.()?.preflight??this._startStatus?.preflight??null;if(e)return e;let t=this._startStatus??this.dashboardStartStatus?.()??null;return t?.selected_room_ids||t?.blocked_rooms||t?.modified_rooms?t:null},i.setStartConfirmation=function(e=null,t=null){this._startConfirmation={preflight:e??this.startPreflight(),confirmToken:t??e?.confirm_token??null}},i.clearStartConfirmation=function(){this._startConfirmation=null},i.startConfirmation=function(){return this._startConfirmation??null},i.startRequiresConfirmation=function(){return!!(this._startConfirmation?.confirmToken||this._startConfirmation?.preflight?.requires_confirmation)},i.startConfirmationToken=function(){return this._startConfirmation?.confirmToken??this._startConfirmation?.preflight?.confirm_token??null},i.requestCancelRunConfirmation=function(){this._cancelRunConfirmation=!0},i.clearCancelRunConfirmation=function(){this._cancelRunConfirmation=!1},i.cancelRunRequiresConfirmation=function(){return this._cancelRunConfirmation===!0},i.hasActiveRun=function(){let e=String(this.vacuumState()??"").toLowerCase();return e==="cleaning"||e==="paused"?!0:this._dashboardJobIsActive?.()??!1},i.shouldShowLiveQueue=function(){return(this.dashboardJobProgressTimeline?.()??[]).length>0&&this.hasActiveRun()},i.canPauseRun=function(){return String(this.vacuumState()??"").toLowerCase()==="cleaning"},i.canResumeRun=function(){return String(this.vacuumState()??"").toLowerCase()==="paused"},i.activeMapId=function(){let e=ve.activeMap(this.vacuumEntityId()),t=this.stateOf(e);if(t&&!Ee.has(String(t)))return String(t);let r=this._findRoomSwitchEntities();return r.length>0?String(r[0].attributes.map_id??"1"):"1"},i.queueChipLongPressMs=function(){let e=Number(this.config?.theme?.queue_chip_long_press_ms),t=Number(this.config?.queue_chip_long_press_ms),r=Number.isFinite(e)?e:Number.isFinite(t)?t:450;return Math.min(1e3,Math.max(250,r))},i._findRoomSwitchEntities=function(){let e=this.hass,t=this.vacuumEntityId();if(!e?.states||!t)return[];let r=[];for(let[a,n]of Object.entries(e.states)){if(!a.startsWith("switch."))continue;let c=n?.attributes;c&&c.vacuum_entity_id===t&&c.room_id!=null&&c.map_id!=null&&"enabled"in c&&r.push({entityId:a,state:n.state,attributes:c})}return r},i._findRoomOrderNumberEntities=function(){let e=this.hass,t=this.vacuumEntityId();if(!e?.states||!t)return[];let r=[];for(let[a,n]of Object.entries(e.states)){if(!a.startsWith("number."))continue;let c=n?.attributes;c&&c.vacuum_entity_id===t&&c.room_id!=null&&c.map_id!=null&&r.push({entityId:a,state:n.state,attributes:c})}return r},i.findRoomOrderNumberEntityId=function(e,t){let r=Object.values(this.hass?.states??{}),a=String(e),n=String(t),c=r.filter(o=>{if(!o?.entity_id?.startsWith("number."))return!1;let l=o.attributes??{};return String(l.map_id)===a&&String(l.room_id)===n});return c.find(o=>String(o.entity_id).toLowerCase().endsWith("_order"))?.entity_id??c[0]?.entity_id??null},i.findRoomSwitchEntityId=function(e,t){let r=this._findRoomSwitchEntities(),a=String(t),n=String(e);return r.find(s=>String(s.attributes.map_id)===n&&String(s.attributes.room_id)===a)?.entityId??null},i.getRoomsForActiveMap=function(){let e=this.activeMapId();return this.getRoomsForMap(e)},i.getRoomsForMap=function(e){let t=this._findRoomSwitchEntities(),r=this._findRoomOrderNumberEntities(),a={};for(let c of r){if(String(c.attributes.map_id)!==String(e))continue;let s=String(c.attributes.room_id),o=Number(c.state),l=String(c.entityId).toLowerCase().endsWith("_order");Number.isFinite(o)&&(!(s in a)||l)&&(a[s]=o)}let n=t.filter(c=>String(c.attributes.map_id)===String(e)).map(c=>{let s=String(c.attributes.room_id),o=c.state==="on",l=s in a?a[s]:c.attributes.order;return this._normalizeRoom(c.attributes,o,l)});return n.sort((c,s)=>{let o=(c.order??999)-(s.order??999);return o!==0?o:String(c.name).localeCompare(String(s.name))}),n},i._normalizeRoom=function(e,t,r=null){let a=Number(e.room_id),n=String(e.map_id??""),c=String(e.room_name??`Room ${e.room_id}`),s=e.slug??null,o=t!==void 0?!!t:!!e.enabled,l=Number(r??e.order??999),d=String(e.profile_name??"vacuum_quick"),u=e.profile_label??null,v=e.profile_subtitle??null,m=String(e.floor_type??""),p=e.floor_type_label??null,f=String(e.carpet_type??""),h=e.carpet_type_label??null,y=!!(e.carpet??(()=>{let U=String(m).toLowerCase();return U==="carpet"||U.startsWith("carpet_")||U.startsWith("carpet-")})()),x=e.clean_mode??"vacuum",w=e.fan_speed??null,g=e.water_level??null,R=e.clean_intensity??null,S=Number(e.clean_passes??1),P=!!(e.edge_mopping??!1),O=e.clean_mode_label??null,W=e.fan_speed_label??null,ae=e.water_level_label??null,oe=e.clean_intensity_label??e.path_type_label??null,H=e.clean_passes_label??null,se=e.edge_mopping_label??null,X=String(x??"").toLowerCase(),ie=X==="vacuum",A=X==="mop"||X==="vacuum_mop"||X.includes("mop")||X.includes("wash"),L=!!(e.is_dock_room??e.isDockRoom??!1),z=!!(e.is_transition??e.isTransition??!1),F=!!(e.transition_candidate??e.transitionCandidate??!1),M=Number(e.transition_score??e.transitionScore??0),C=this._normalizeRoomReferenceList(e.grants_access_to??e.grantsAccessTo),j=this._normalizeRoomReferenceList(e.requires_access_from??e.requiresAccessFrom),V=e.rules??e.automation_rules,le=Array.isArray(V)?V:[];return{id:a,mapId:n,name:c,slug:s,enabled:o,order:l,profileName:d,profileLabel:u,profileSubtitle:v,floorType:m,floorTypeLabel:p,carpetType:f,carpetTypeLabel:h,carpet:y,cleanMode:x,cleanModeLabel:O,fanSpeed:w,fanSpeedLabel:W,waterLevel:g,waterLevelLabel:ae,cleanIntensity:R,cleanIntensityLabel:oe,cleanPasses:S,cleanPassesLabel:H,edgeMopping:P,edgeMoppingLabel:se,isCustomProfile:d.toLowerCase()==="custom",isVacuumOnly:ie,isMopCapable:A,isDockRoom:L,isTransition:z,transitionCandidate:F,transitionScore:M,rules:le,profile:d,passes:S,grantsAccessTo:C,requiresAccessFrom:j,profile_name:d,floor_type:m,floor_type_label:p,carpet_type:f,carpet_type_label:h,clean_mode:x,clean_mode_label:O,fan_speed:w,fan_speed_label:W,water_level:g,water_level_label:ae,clean_intensity:R,clean_intensity_label:oe,clean_passes:S,clean_passes_label:H,edge_mopping:P,edge_mopping_label:se,map_id:n,room_id:a,room_name:c,grants_access_to:C,requires_access_from:j,is_transition:z,transition_candidate:F,transition_score:M}},i._roomModeIncludesMop=function(e){let t=String(e??"").toLowerCase();return t==="mop"||t==="vacuum_mop"||t.includes("mop")||t.includes("wash")},i.enabledRoomCount=function(){return this.getRoomsForActiveMap().filter(e=>e.enabled).length},i._startStatusFlag=function(e){let t=this.dashboardJobControl?.()?.[e]??this.dashboardStartStatus?.()?.[e]??this._startStatus?.[e];if(typeof t=="boolean")return t;if(t==null)return!1;let r=String(t).trim().toLowerCase();return r==="true"||r==="1"||r==="yes"},i._localStartBlockReason=function(){if(this.enabledRoomCount()<1)return"No rooms included.";let e=String(this.vacuumState()??"").toLowerCase();return e==="cleaning"?"Already cleaning.":e==="returning"?"Returning to dock.":e==="error"?"Vacuum has an error.":null},i.canStartCleaning=function(){if(this._localStartBlockReason()&&!this.startRequiresConfirmation())return!1;let t=this.dashboardJobControl?.();return t&&t.can_start!=null?!!t.can_start:this._startStatus?!this._startStatusFlag("blocked"):!0},i.startBlockedReason=function(){if(this.startRequiresConfirmation())return null;let e=this._localStartBlockReason();if(e)return e;let t=this.dashboardJobControl?.();if(t){if(this._startStatusFlag("blocked"))return t.message??t.reason_detail??t.reason??"Start is blocked.";if(this._startStatusFlag("warning"))return t.message??t.reason_detail??null}return this._startStatus||this.dashboardStartStatus?.()?this._startStatusFlag("blocked")?this.dashboardStartStatus?.()?.message??this._startStatus?.message??"Start is blocked.":this._startStatusFlag("warning")?this.dashboardStartStatus?.()?.message??this._startStatus?.message??null:null:null},i.hasStartWarning=function(){return this._localStartBlockReason()?!1:this._startStatusFlag("warning")},i.startStatusReason=function(){return this.dashboardJobControl?.()?.reason??this.dashboardStartStatus?.()?.reason??this._startStatus?.reason??null},i.activeJobRooms=function(){let e=this.dashboardJobProgressTimeline?.()??[];if(this.shouldShowLiveQueue())return e.map((a,n)=>({jobOrder:a.position??n+1,name:a.room_name??`Room ${a.room_id??n+1}`}));let t=String(this.vacuumState()??"").toLowerCase();return new Set(["docked","idle","error"]).has(t)&&this._activeJobRooms?.length&&(this._activeJobRooms=null),this._activeJobRooms??null}}function Qt(i){i.getOrderAdapter=function(e){return e!=="rooms"?null:{scope:"rooms",getItems:function(){let t=this.getRoomsForActiveMap();return Array.isArray(t)?t:[]},getId:function(t){return t?.id},getLabel:function(t){return t?.name??"Room"},getOrder:function(t){return t?.order},setOrder:function(t,r){return{...t,order:r}},persist:async function(t,r={}){if(!this._actions?.persistRoomOrdering){console.warn("[eufy-vacuum-command-center] persistRoomOrdering not available");return}await this._actions.persistRoomOrdering(t,r)}}}}function Xt(i){i.openRoomAccess=function(e,t){let r=this.getRoomsForMap(t).find(a=>String(a.id)===String(e)&&String(a.mapId)===String(t));r&&(this._roomAccessRoomId=r.id,this._roomAccessMapId=r.mapId,this._roomAccessFields={is_dock_room:r.isDockRoom??!1,grants_access_to:[...r.grantsAccessTo??[]]},this._roomAccessSaveError=null)},i.closeRoomAccess=function(){this._roomAccessRoomId=null,this._roomAccessMapId=null,this._roomAccessFields=null,this._roomAccessSaveError=null},i.isRoomAccessOpen=function(){return this._roomAccessRoomId!=null},i.activeAccessRoom=function(){return!this._roomAccessRoomId||!this._roomAccessMapId?null:this.getRoomsForMap(this._roomAccessMapId).find(e=>String(e.id)===String(this._roomAccessRoomId)&&String(e.mapId)===String(this._roomAccessMapId))??null},i.roomAccessFields=function(){return this._roomAccessFields??{grants_access_to:[]}},i.setRoomAccessSaveError=function(e){this._roomAccessSaveError=e??null},i.roomAccessSaveError=function(){return this._roomAccessSaveError??null},i.accessEditableRooms=function(){let e=this.activeAccessRoom();if(!e)return[];let t=this.getRoomsForMap(e.mapId),r=new Set(this._normalizeRoomReferenceList(this.roomAccessFields().grants_access_to)),a=this._buildClaimedTargetMap(t,String(e.id)),n=t.filter(o=>{if(String(o.id)===String(e.id)||o.isDockRoom)return!1;let l=String(o.id),d=a.get(l);return r.has(l)||!d}).map(o=>({id:String(o.id),name:o.name,missing:!1,available:!0,claimedBy:null})),c=new Set(n.map(o=>o.id)),s=Array.from(r).filter(o=>!c.has(String(o))).map(o=>({id:String(o),name:`Missing Room ${o}`,missing:!0,available:!0,claimedBy:null}));return[...n,...s]},i.accessInboundRooms=function(){let e=this.activeAccessRoom();if(!e)return[];let t=this.getRoomsForMap(e.mapId),r=String(e.id);return t.filter(a=>this._normalizeRoomReferenceList(a.grantsAccessTo).includes(r)).map(a=>({id:String(a.id),name:a.name,missing:!1}))},i.toggleRoomAccessTarget=function(e){if(!this._roomAccessFields)return;let t=String(e??"").trim();if(!t)return;let r=new Set(this._normalizeRoomReferenceList(this._roomAccessFields.grants_access_to));r.has(t)?r.delete(t):r.add(t),this._roomAccessFields={...this._roomAccessFields,grants_access_to:Array.from(r)},this._roomAccessSaveError=null},i.toggleIsDockRoomField=function(){this._roomAccessFields&&(this._roomAccessFields={...this._roomAccessFields,is_dock_room:!this._roomAccessFields.is_dock_room},this._roomAccessSaveError=null)},i.roomAccessValidation=function(){let e=this.activeAccessRoom();return e?this.roomAccessFields().is_dock_room?{valid:!0,issues:[],normalizedGrantsAccessTo:[]}:this.validateRoomAccessUpdate(e.mapId,e.id,this.roomAccessFields().grants_access_to??[]):{valid:!1,issues:[{code:"missing_room",message:"No room is selected for access editing."}],normalizedGrantsAccessTo:[]}}}function Zt(i){i.openRoomEstimateModal=function(e,t){let r=this.getRoomsForMap(t).find(a=>String(a.id)===String(e)&&String(a.mapId)===String(t));r&&(this._roomEstimateModalRoomId=r.id,this._roomEstimateModalMapId=r.mapId)},i.closeRoomEstimateModal=function(){this._roomEstimateModalRoomId=null,this._roomEstimateModalMapId=null},i.isRoomEstimateModalOpen=function(){return this._roomEstimateModalRoomId!=null},i.activeRoomEstimateRoom=function(){return!this._roomEstimateModalRoomId||!this._roomEstimateModalMapId?null:this.getRoomsForMap(this._roomEstimateModalMapId).find(e=>String(e.id)===String(this._roomEstimateModalRoomId)&&String(e.mapId)===String(this._roomEstimateModalMapId))??null},i.activeRoomEstimateDetails=function(){let e=this.activeRoomEstimateRoom?.();if(!e)return null;let t=String(e.id),a=(Array.isArray(this.learningRoomTimeline?.())?this.learningRoomTimeline():[]).find(s=>String(s?.room_id)===t)??null,n=this.roomEstimateForRoom?.(e.id)??null,c=this.dashboardPlannedWaterRoomForRoom?.(e.id,e.slug)??null;return{room:e,entry:a,roomEstimate:n,plannedWaterRoom:c,confidenceBreakpoint:a?.confidence_breakpoint??n?.confidence_breakpoint??null,confidenceLabel:a?.confidence_label??n?.confidence_label??null}}}function er(i){i.openRoomEditor=function(e,t){let a=this.getRoomsForActiveMap().find(n=>String(n.id)===String(e)&&String(n.mapId)===String(t));a&&(this._roomEditorRoomId=a.id,this._roomEditorMapId=a.mapId,this._roomEditorFields={clean_mode:this._canonicalCleanModeDisplay(a.cleanMode??"vacuum"),fan_speed:a.fanSpeed??null,water_level:(()=>{let n=a.waterLevel??null;return String(n??"").trim().toLowerCase()==="off"?null:n})(),clean_intensity:a.cleanIntensity??a.selected_profile_details?.clean_intensity??"Quick",clean_passes:a.cleanPasses??1,edge_mopping:a.edgeMopping??!1,profile_name:a.profileName??"vacuum_quick"},this._syncEditorProfileFromFields())},i.closeRoomEditor=function(){this._roomEditorRoomId=null,this._roomEditorMapId=null,this._roomEditorFields=null,this._skipRefreshOnClose=!1},i.setSkipRefreshOnClose=function(e){this._skipRefreshOnClose=!!e},i.shouldSkipRefreshOnClose=function(){return!!this._skipRefreshOnClose},i.isRoomEditorOpen=function(){return this._roomEditorRoomId!=null},i.activeEditorRoom=function(){return this._roomEditorRoomId?this.getRoomsForActiveMap().find(t=>String(t.id)===String(this._roomEditorRoomId)&&String(t.mapId)===String(this._roomEditorMapId))??null:null},i.editorFields=function(){return this._roomEditorFields??null},i.availableEditorProfiles=function(){return this.roomProfilesLibrary?.()??{}},i.editorProfileLabels=function(){return Object.fromEntries(this.roomProfilesList?.().map(e=>[e.name,e.label])??[])},i.getEditorProfileDefinition=function(e){return this.roomProfileDefinition?.(e)??null},i._profileDerivedOptions=function(e){let t=this.availableEditorProfiles(),r=new Set;return Object.values(t).forEach(a=>{let n=a?.[e];n!=null&&String(n).trim()!==""&&r.add(String(n))}),Array.from(r)},i._normalizeOptionList=function(e){let t=new Set,r=[];for(let a of e??[]){let n=String(a??"").trim();if(!n)continue;let c=n.toLowerCase();t.has(c)||(t.add(c),r.push(n))}return r},i._canonicalCleanModeDisplay=function(e){let t=String(e??"").trim(),r=t.toLowerCase().replace(/[\s+_-]+/g,"");return r==="vacuummop"||r==="vacuumandmop"?"Vacuum and mop":r==="vacuum"?"Vacuum":r==="mop"?"Mop":t},i._canonicalCleanModeCompare=function(e){let t=String(e??"").trim().toLowerCase().replace(/[\s+_-]+/g,"");return t==="vacuummop"||t==="vacuumandmop"?"vacuum_mop":t==="vacuum"?"vacuum":t==="mop"?"mop":t},i._profileIntensityToEditorIntensity=function(e){let t=String(e??"").trim().toLowerCase();return t==="quick"?"Quick":t==="deep"?"Narrow":e??null},i._editorIntensityToComparableProfileIntensity=function(e){let t=String(e??"").trim().toLowerCase();return t==="quick"?"quick":t==="narrow"?"deep":t},i._normalizeEditorComparisonValue=function(e,t=""){if(t==="clean_mode")return this._canonicalCleanModeCompare(e);if(t==="clean_intensity")return this._editorIntensityToComparableProfileIntensity(e);if(e==null)return null;if(typeof e=="boolean")return e;if(typeof e=="number")return Number(e);let r=String(e).trim(),a=r.toLowerCase();if(a==="true")return!0;if(a==="false")return!1;let n=Number(r);return!Number.isNaN(n)&&r!==""?n:a},i._buildComparableProfileFields=function(e){let t=this.isEditorRoomCarpet(),r=this._canonicalCleanModeDisplay(e?.clean_mode??"vacuum"),a=this.isMopMode(r)&&!t;return{clean_mode:r,fan_speed:e?.fan_speed??null,water_level:a?e?.water_level??null:null,clean_intensity:this._profileIntensityToEditorIntensity(e?.clean_intensity??null),clean_passes:Number(e?.clean_passes??1),edge_mopping:a?!!e?.edge_mopping:!1}},i._editorFieldsMatchProfile=function(e,t){if(!e||!t)return!1;let r=this._buildComparableProfileFields(t);return this._normalizeEditorComparisonValue(e.clean_mode,"clean_mode")===this._normalizeEditorComparisonValue(r.clean_mode,"clean_mode")&&this._normalizeEditorComparisonValue(e.fan_speed)===this._normalizeEditorComparisonValue(r.fan_speed)&&this._normalizeEditorComparisonValue(e.water_level)===this._normalizeEditorComparisonValue(r.water_level)&&this._normalizeEditorComparisonValue(e.clean_intensity,"clean_intensity")===this._normalizeEditorComparisonValue(r.clean_intensity,"clean_intensity")&&this._normalizeEditorComparisonValue(e.clean_passes)===this._normalizeEditorComparisonValue(r.clean_passes)&&this._normalizeEditorComparisonValue(e.edge_mopping)===this._normalizeEditorComparisonValue(r.edge_mopping)},i.matchingEditorProfileName=function(e=null){let t=e??this.editorFields();if(!t)return null;let r=this.availableEditorProfiles();for(let[a,n]of Object.entries(r))if(this._editorFieldsMatchProfile(t,n))return a;return null},i._syncEditorProfileFromFields=function(){if(!this._roomEditorFields)return;let e=this.matchingEditorProfileName(this._roomEditorFields);this._roomEditorFields={...this._roomEditorFields,profile_name:e??"custom"}},i.applyEditorProfile=function(e){if(!this._roomEditorFields)return;let t=this.getEditorProfileDefinition(e);if(!t)return;let r=this._canonicalCleanModeDisplay(t.clean_mode??this._roomEditorFields.clean_mode??"vacuum"),a=this.isEditorRoomCarpet(),n=this.isMopMode(r)&&!a;this._roomEditorFields={...this._roomEditorFields,profile_name:String(e),clean_mode:r,fan_speed:t.fan_speed??null,water_level:n?t.water_level??null:null,clean_intensity:this._profileIntensityToEditorIntensity(t.clean_intensity??null),clean_passes:Number(t.clean_passes??1),edge_mopping:n?!!t.edge_mopping:!1}},i.updateEditorField=function(e,t){if(!this._roomEditorFields)return;if(e==="profile_name"){t==="custom"?this._roomEditorFields={...this._roomEditorFields,profile_name:"custom"}:this.applyEditorProfile(t);return}let r=e==="clean_mode"?this._canonicalCleanModeDisplay(t):t;this._roomEditorFields={...this._roomEditorFields,[e]:r},e==="clean_mode"&&!this.isMopMode(r)&&(this._roomEditorFields.water_level=null,this._roomEditorFields.edge_mopping=!1),e==="clean_mode"&&this.isEditorRoomCarpet()&&(this._roomEditorFields.water_level=null,this._roomEditorFields.edge_mopping=!1),this._syncEditorProfileFromFields()},i.isMopMode=function(e){let t=this._canonicalCleanModeCompare(e);return t.includes("mop")||t.includes("wash")},i.isEditorRoomCarpet=function(){let e=this.activeEditorRoom();if(!e)return!1;if(e.carpet===!0)return!0;let t=String(e.floorType??"").toLowerCase();return t==="carpet"||t.startsWith("carpet_")||t.startsWith("carpet-")},i.showWaterLevel=function(){if(this.isEditorRoomCarpet())return!1;let e=this.editorFields();return e?this.isMopMode(e.clean_mode):!1},i.showEdgeMopping=function(){if(this.isEditorRoomCarpet())return!1;let e=this.editorFields();return e?this.isMopMode(e.clean_mode):!1},i.cleanModeOptions=function(){let t=`select.${this.vacuumObjectId()}_cleaning_mode`,r=this.attrsOf(t)?.options??[],a=this._profileDerivedOptions("clean_mode"),n=[...r,...a,"vacuum","vacuum_mop"].map(s=>this._canonicalCleanModeDisplay(s));return this._normalizeOptionList(n).filter(s=>{let o=String(s).toLowerCase().replace(/[\s_-]/g,"");return!(o.includes("mopaftersweep")||o.includes("afterswee")||this.isEditorRoomCarpet()&&this.isMopMode(s))})},i.suctionLevelOptions=function(){let t=`select.${this.vacuumObjectId()}_suction_level`,r=this.attrsOf(t)?.options??[],a=this._profileDerivedOptions("fan_speed");return this._normalizeOptionList([...r,...a,"Quiet","Standard","Turbo","Max"]).filter(n=>String(n).toLowerCase().replace(/[\s_-]/g,"")!=="boostiq")},i.waterLevelOptions=function(){let t=`select.${this.vacuumObjectId()}_water_level`,r=this.attrsOf(t)?.options??[],a=this._profileDerivedOptions("water_level");return this._normalizeOptionList([...r,...a,"Low","Medium","High"]).filter(n=>String(n??"").trim().toLowerCase().replace(/[\s_-]/g,"")!=="off")},i.cleanIntensityOptions=function(){let e=this.activeEditorRoom();if(e?.slug){let r=`input_select.${this.vacuumObjectId()}_map_${e.mapId}_cleaning_speed_${e.slug}`,a=this.attrsOf(r)?.options??[],n=this._normalizeOptionList(a);if(n.length)return n}return this._normalizeOptionList(["Quick","Normal","Narrow"])},i.isCustomProfile=function(){let e=this.editorFields();return e?String(e.profile_name??"").toLowerCase()==="custom":!1},i.currentEditorManagedProfileName=function(){let e=this.editorFields();if(!e)return null;let t=String(e.profile_name??"").trim();return!t||t.toLowerCase()==="custom"?null:t}}var ke=new Set(["is_on","is_off","exists","missing"]),Ya=["is_on","is_off","exists","missing"],Qa=["equals","not_equals","in","not_in","exists","missing"],Xa=["equals","not_equals","gt","gte","lt","lte","exists","missing"],Za=["equals","not_equals","in","not_in","exists","missing"],Be=["is_on","is_off","exists","missing","equals","not_equals","gt","gte","lt","lte","in","not_in"];function ei(){return{id:null,label:"",entity_id:"",kind:"blocker",operator:"is_on",value:null,enabled:!0,effect:{action:"exclude",reason:"",changes:{}}}}function we(i){if(i==null||i==="")return!1;if(typeof i=="number")return Number.isFinite(i);let e=String(i).trim();return e?Number.isFinite(Number(e)):!1}function je(i){if(Array.isArray(i))return i.map(t=>String(t??"").trim()).filter(Boolean);let e=String(i??"").trim();return e?e.split(",").map(t=>t.trim()).filter(Boolean):[]}function tr(i,e,t){if(ke.has(String(t??"")))return null;let r=e?.valueModeForOperator?.(t)??"text";if(r==="multi-select")return je(i);if(r==="number"){if(i==null||i==="")return null;let a=Number(i);return Number.isFinite(a)?a:i}return i}function Se(i,e){if(!i)return i;let t=e?.operators??Be,r=t[0]??"equals",a=t.includes(i.operator)?i.operator:r,n=tr(i.value,e,a);if(e?.category==="enum"){let c=new Set((e.options??[]).map(o=>String(o.value))),s=e.valueModeForOperator?.(a);s==="single-select"&&n!=null&&!c.has(String(n))&&(n=null),s==="multi-select"&&(n=je(n).filter(o=>c.has(String(o))))}return{...i,operator:a,value:n}}function ti(i){return Array.isArray(i)?i.join(", "):i}function ri(i,e,t){if(!t)return 0;let r=String(i??"").toLowerCase(),a=String(e??"").toLowerCase();return r===t?100:a===t?95:r.startsWith(t)?80:a.startsWith(t)?70:r.includes(t)?50:a.includes(t)?40:0}function rr(i){i.roomRulesActiveRoomId=function(){return this._roomRulesActiveRoomId??null},i.setRoomRulesActiveRoom=function(e){let t=String(e??"").trim();this._roomRulesActiveRoomId=t||null,this._roomRulesDraft=null,this._roomRulesDraftMode=null,this._roomRulesSaveError=null},i.resolvedRoomRulesRoom=function(){let e=this.getRoomsForActiveMap?.()??[];if(!e.length)return null;let t=this._roomRulesActiveRoomId;if(t){let r=e.find(a=>String(a.id)===String(t));if(r)return r}return e[0]},i.rulesForActiveRoomTab=function(){let e=this.resolvedRoomRulesRoom();return e?Array.isArray(e.rules)?e.rules:[]:[]},i.roomRulesDraft=function(){return this._roomRulesDraft??null},i.roomRulesDraftMode=function(){return this._roomRulesDraftMode??null},i.openNewRuleDraft=function(){this._roomRulesDraft=Se(ei(),this.ruleEntityDescriptor("")),this._roomRulesDraftMode="new",this._roomRulesSaveError=null},i.openEditRuleDraft=function(e){e&&(this._roomRulesDraft=Se({id:e.id??null,label:e.label??"",entity_id:e.entity_id??"",kind:e.kind??"blocker",operator:e.operator??"is_on",value:e.value??null,enabled:e.enabled!==!1,effect:{action:e.effect?.action??(e.kind==="modifier"?"mutate":"exclude"),reason:e.effect?.reason??"",changes:{...e.effect?.changes??{}}}},this.ruleEntityDescriptor(e.entity_id??"")),this._roomRulesDraftMode="edit",this._roomRulesSaveError=null)},i.closeRulesDraft=function(){this._roomRulesDraft=null,this._roomRulesDraftMode=null,this._roomRulesSaveError=null},i.updateRuleDraftField=function(e,t){if(this._roomRulesDraft){if(e==="kind"){let r=t==="modifier"?"modifier":"blocker";this._roomRulesDraft=Se({...this._roomRulesDraft,kind:r,effect:{...this._roomRulesDraft.effect,action:r==="modifier"?"mutate":"exclude",changes:r==="blocker"?{}:this._roomRulesDraft.effect.changes}},this.ruleEntityDescriptor(this._roomRulesDraft.entity_id))}else if(e==="operator")this._roomRulesDraft=Se({...this._roomRulesDraft,operator:String(t??"is_on"),value:ke.has(String(t))?null:this._roomRulesDraft.value},this.ruleEntityDescriptor(this._roomRulesDraft.entity_id));else if(e==="enabled")this._roomRulesDraft={...this._roomRulesDraft,enabled:!!t};else if(e==="entity_id")this._roomRulesDraft=Se({...this._roomRulesDraft,entity_id:String(t??"")},this.ruleEntityDescriptor(t));else if(e==="effect.reason")this._roomRulesDraft={...this._roomRulesDraft,effect:{...this._roomRulesDraft.effect,reason:String(t??"")}};else if(e.startsWith("effect.changes.")){let r=e.slice(15),a={...this._roomRulesDraft.effect.changes??{}};t==null?delete a[r]:a[r]=t,this._roomRulesDraft={...this._roomRulesDraft,effect:{...this._roomRulesDraft.effect,changes:a}}}else{let r=this.ruleEntityDescriptor(this._roomRulesDraft.entity_id);this._roomRulesDraft={...this._roomRulesDraft,[e]:e==="value"?tr(t,r,this._roomRulesDraft.operator):t}}this._roomRulesSaveError=null}},i.roomRulesDraftIsValid=function(){let e=this._roomRulesDraft;if(!e)return!1;let t=String(e.entity_id??"").trim();if(!t)return!1;let r=this.ruleEntityDescriptor(t);if(!r.entityExists||!(r.operators??[]).includes(e.operator))return!1;if(!ke.has(String(e.operator??""))){let a=r.valueModeForOperator?.(e.operator)??"text";if(a==="multi-select"){if(!je(e.value).length)return!1}else if(a==="number"){if(!we(e.value))return!1}else if(!String(e.value??"").trim())return!1}if(e.kind==="modifier"){let a=e.effect?.changes??{};if(!Object.entries(a).filter(([c,s])=>s==null?!1:c==="clean_passes"?Number(s)===1||Number(s)===2:!0).length)return!1}return!0},i.roomRulesSaveError=function(){return this._roomRulesSaveError??null},i.setRoomRulesSaveError=function(e){this._roomRulesSaveError=e??null},i.ruleEntityDescriptor=function(e=null){let t=typeof e=="string"?e:e?.entity_id??this._roomRulesDraft?.entity_id??"",r=String(t??"").trim(),a=r?this.entity?.(r):null,n=a?.attributes??{},c=r.includes(".")?r.split(".")[0]:"",s=a?.state??null,o=Array.isArray(n.options)?n.options.map(u=>({value:String(u??""),label:String(u??"")})):[],l="unknown";["binary_sensor","switch","input_boolean"].includes(c)?l="boolean":["select","input_select"].includes(c)||o.length?l="enum":["number","input_number"].includes(c)?l="numeric":c==="sensor"?l=we(s)?"numeric":"text":String(s??"").toLowerCase()==="on"||String(s??"").toLowerCase()==="off"?l="boolean":r&&(l="text");let d=l==="boolean"?Ya:l==="enum"?Qa:l==="numeric"?Xa:l==="text"?Za:Be;return{entityId:r,entityExists:!!a,entityLabel:String((n.friendly_name??r)||"Entity"),currentState:s,category:l,operators:d,options:o,min:we(n.min)?Number(n.min):null,max:we(n.max)?Number(n.max):null,step:we(n.step)?Number(n.step):null,unit:n.unit_of_measurement??null,valueModeForOperator(u){return ke.has(String(u??""))||l==="boolean"?"none":l==="enum"?u==="in"||u==="not_in"?"multi-select":"single-select":l==="numeric"?"number":"text"}}},i.ruleOperatorGroups=function(e=null){let t=this.ruleEntityDescriptor(e),r=new Set(t.operators??Be);return[{label:"State",operators:[{value:"is_on",label:"Is ON"},{value:"is_off",label:"Is OFF"}]},{label:"Existence",operators:[{value:"exists",label:"Exists"},{value:"missing",label:"Missing"}]},{label:"Equality",operators:[{value:"equals",label:"Equals"},{value:"not_equals",label:"Not equals"}]},{label:"Numeric",operators:[{value:"gt",label:">"},{value:"gte",label:"\u2265"},{value:"lt",label:"<"},{value:"lte",label:"\u2264"}]},{label:"List",operators:[{value:"in",label:"In list"},{value:"not_in",label:"Not in list"}]}].map(n=>({...n,operators:n.operators.filter(c=>r.has(c.value))})).filter(n=>n.operators.length>0)},i.ruleEntitySearchResults=function(e=null,t=12){let r=String(e??this._roomRulesDraft?.entity_id??"").trim().toLowerCase();return r.length<2?[]:Object.entries(this.hass?.states??{}).map(([n,c])=>{let s=String(c?.attributes?.friendly_name??"").trim(),o=ri(n,s,r);return o<=0?null:{entity_id:n,friendly_name:s,state:c?.state??null,domain:n.split(".")[0]??"",score:o}}).filter(Boolean).sort((n,c)=>c.score!==n.score?c.score-n.score:n.entity_id.localeCompare(c.entity_id)).slice(0,Math.max(1,Number(t)||12))},i.roomRulesForRoom=function(e){let r=(this.getRoomsForActiveMap?.()??[]).find(a=>String(a.id)===String(e));return r?Array.isArray(r.rules)?r.rules:[]:[]},i.ruleConditionSummary=function(e){let t=e.operator??"",r=ti(e.value);switch(t){case"is_on":return"is ON";case"is_off":return"is OFF";case"exists":return"exists";case"missing":return"is missing";case"equals":return`= ${r??""}`;case"not_equals":return`!= ${r??""}`;case"gt":return`> ${r??""}`;case"gte":return`>= ${r??""}`;case"lt":return`< ${r??""}`;case"lte":return`<= ${r??""}`;case"in":return`in [${r??""}]`;case"not_in":return`not in [${r??""}]`;default:return t}},i.ruleEffectSummary=function(e){if(e.kind==="blocker"){let a=e.effect?.reason;return a?`Exclude - ${a}`:"Exclude room"}let t=e.effect?.changes??{},r=[];return t.clean_mode&&r.push(`mode: ${t.clean_mode}`),t.fan_speed&&r.push(`fan: ${t.fan_speed}`),t.water_level&&r.push(`water: ${t.water_level}`),t.clean_intensity&&r.push(`intensity: ${t.clean_intensity}`),t.clean_passes!=null&&r.push(`passes: ${t.clean_passes}`),t.edge_mopping!=null&&r.push(`edge mop: ${t.edge_mopping?"on":"off"}`),r.length?r.join(", "):"Modify settings"}}var ze={MAINTENANCE:"maintenance_items",REPLACEMENTS:"replacements"};function ar(i){i._ensureMaintenanceState=function(){return this._maintenanceState||(this._maintenanceState={activeTab:ze.MAINTENANCE,modalItem:null,resetUi:{confirming:!1,pending:!1,success:"",error:""}}),this._maintenanceState},i.maintenanceActiveTab=function(){return this._ensureMaintenanceState().activeTab},i.setMaintenanceActiveTab=function(e){let t=this._ensureMaintenanceState(),r=String(e??"").trim().toLowerCase();r!==ze.MAINTENANCE&&r!==ze.REPLACEMENTS||(t.activeTab=r)},i.isMaintenanceTabActive=function(e){return this.maintenanceActiveTab()===String(e??"").trim().toLowerCase()},i.openMaintenanceModal=function(e){if(!e||typeof e!="object")return;let t=this._ensureMaintenanceState();t.modalItem={...e},t.resetUi={confirming:!1,pending:!1,success:"",error:""}},i.closeMaintenanceModal=function(){let e=this._ensureMaintenanceState();e.modalItem=null,e.resetUi={confirming:!1,pending:!1,success:"",error:""}},i.activeMaintenanceModalItem=function(){return this._ensureMaintenanceState().modalItem??null},i.isMaintenanceModalOpen=function(){return!!this.activeMaintenanceModalItem()},i.maintenanceResetUi=function(){return this._ensureMaintenanceState().resetUi},i.beginMaintenanceResetConfirmation=function(){let e=this.maintenanceResetUi();e.confirming=!0,e.error="",e.success=""},i.cancelMaintenanceResetConfirmation=function(){let e=this.maintenanceResetUi();e.confirming=!1,e.pending=!1,e.error=""},i.setMaintenanceResetPending=function(e){this.maintenanceResetUi().pending=!!e},i.setMaintenanceResetSuccess=function(e){let t=this.maintenanceResetUi();t.success=String(e??""),t.error="",t.pending=!1,t.confirming=!1},i.setMaintenanceResetError=function(e){let t=this.maintenanceResetUi();t.error=String(e??""),t.success="",t.pending=!1},i.canInvokeMaintenanceReset=function(e){return e?.can_reset===!0&&typeof e?.reset_service=="string"&&e.reset_service.length>0&&e?.reset_service_data!=null},i.findUpkeepItem=function(e,t,r=null){let a=this.dashboardUpkeep?.()??{},n=String(e??"").trim().toLowerCase(),c=String(t??"").trim().toLowerCase(),s=r==null?null:String(r).trim().toLowerCase();return[...Array.isArray(a.maintenance_items)?a.maintenance_items:[],...Array.isArray(a.replacement_items)?a.replacement_items:[]].find(l=>{let d=String(l?.kind??"").trim().toLowerCase(),u=String(l?.component??"").trim().toLowerCase(),v=l?.entity_id==null?null:String(l.entity_id).trim().toLowerCase();return!(d!==n||u!==c||s&&v&&v!==s)})??null}}var K=["App Shell & Typography","Cards & Surfaces","Borders & Shadows","Chips","Room Cards","Floor Textures","Floor Textures \u2014 Tile","Floor Textures \u2014 Wood","Floor Textures \u2014 Marble","Floor Textures \u2014 Concrete","Floor Textures \u2014 Carpet Low","Floor Textures \u2014 Carpet High","Floor Textures \u2014 Granite","Queue & Ordering","Status, Confidence & Alerts","Learning & Metrics","Modals & Overlays","Shared Foundations"];var ai=Object.freeze(["color","text","shadow","size","number","duration","motion","typography","easing"]),ii=new Set(ai);function ni(i){return String(i||"").replace(/^--evcc-/,"").replace(/-/g," ").replace(/\b\w/g,e=>e.toUpperCase()).trim()}function ci(i,e="color"){return function(r,a=null,n=e){let c=ii.has(n)?n:e;return{key:r,label:a||ni(r),group:i,type:c}}}function q(i,e="color"){let t=ci(i,e);return t.color=(r,a=null)=>t(r,a,"color"),t.text=(r,a=null)=>t(r,a,"text"),t.shadow=(r,a=null)=>t(r,a,"shadow"),t.size=(r,a=null)=>t(r,a,"size"),t.number=(r,a=null)=>t(r,a,"number"),t.duration=(r,a=null)=>t(r,a,"duration"),t.motion=(r,a=null)=>t(r,a,"motion"),t.typography=(r,a=null)=>t(r,a,"typography"),t.easing=(r,a=null)=>t(r,a,"easing"),t}var _e=q("App Shell & Typography","color"),Q=q("Cards & Surfaces","color"),be=q("Borders & Shadows","color"),I=q("Chips","color"),ee=q("Room Cards","color"),bn=q("Floor Textures","number"),E=q("Queue & Ordering","color"),T=q("Status, Confidence & Alerts","color"),k=q("Learning & Metrics","color"),$=q("Modals & Overlays","color"),Y=q("Shared Foundations","size");var ir=[_e.color("--evcc-accent","Accent"),_e.color("--evcc-border","Border"),_e.color("--evcc-text-muted","Text Muted"),_e.color("--evcc-text-primary","Text Primary"),_e.color("--evcc-text-secondary","Text Secondary")];var nr=[Q.color("--evcc-bg-input","BG Input"),Q.color("--evcc-bg-panel","BG Panel"),Q.color("--evcc-card-bg","Card BG"),Q.size("--evcc-card-gap","Card Gap"),Q.size("--evcc-card-min-height","Card Min Height"),Q.size("--evcc-card-padding","Card Padding"),Q.color("--evcc-panel-bg","Panel BG"),Q.color("--evcc-surface-base","Surface Base"),Q.color("--evcc-surface-card","Surface Card"),Q.color("--evcc-surface-input","Surface Input"),Q.color("--evcc-surface-overlay","Surface Overlay"),Q.color("--evcc-surface-panel","Surface Panel"),Q.color("--evcc-surface-raise","Surface Raise"),Q.color("--evcc-surface-raised","Surface Raised")];var cr=[be.color("--evcc-border-default","Border Default"),be.color("--evcc-border-strong","Border Strong"),be.color("--evcc-border-subtle","Border Subtle"),be.shadow("--evcc-shadow-card","Shadow Card"),be.shadow("--evcc-shadow-hover","Shadow Hover")];var sr=[I.color("--evcc-chip-active-bg","Chip Active BG"),I.color("--evcc-chip-active-border","Chip Active Border"),I.color("--evcc-chip-active-text","Chip Active Text"),I.color("--evcc-chip-bg","Chip BG"),I.color("--evcc-chip-border","Chip Border"),I.color("--evcc-chip-excluded-bg","Chip Excluded BG"),I.color("--evcc-chip-excluded-border","Chip Excluded Border"),I.color("--evcc-chip-excluded-text","Chip Excluded Text"),I.size("--evcc-chip-font-size","Chip Font Size"),I.typography("--evcc-chip-font-weight","Chip Font Weight"),I.size("--evcc-chip-gap","Chip Gap"),I.size("--evcc-chip-height","Chip Height"),I.color("--evcc-chip-hover-bg","Chip Hover BG"),I.color("--evcc-chip-hover-border","Chip Hover Border"),I.color("--evcc-chip-hover-text","Chip Hover Text"),I.size("--evcc-chip-icon-height","Chip Icon Height"),I.size("--evcc-chip-icon-padding","Chip Icon Padding"),I.size("--evcc-chip-icon-size","Chip Icon Size"),I.color("--evcc-chip-included-bg","Chip Included BG"),I.color("--evcc-chip-included-border","Chip Included Border"),I.color("--evcc-chip-included-text","Chip Included Text"),I.color("--evcc-chip-neutral-bg","Chip Neutral BG"),I.size("--evcc-chip-padding","Chip Padding"),I.size("--evcc-chip-radius","Chip Radius"),I.color("--evcc-chip-success-bg","Chip Success BG"),I.color("--evcc-chip-success-border","Chip Success Border"),I.color("--evcc-chip-success-text","Chip Success Text"),I.color("--evcc-chip-text","Chip Text"),I.color("--evcc-chip-warning-bg","Chip Warning BG"),I.color("--evcc-chip-warning-border","Chip Warning Border"),I.color("--evcc-chip-warning-text","Chip Warning Text")];var or=[ee.color("--evcc-profile-chip-bg","Profile Chip BG"),ee.color("--evcc-profile-chip-border","Profile Chip Border"),ee.color("--evcc-profile-chip-custom-bg","Profile Chip Custom BG"),ee.color("--evcc-profile-chip-custom-border","Profile Chip Custom Border"),ee.color("--evcc-profile-chip-custom-text","Profile Chip Custom Text"),ee.color("--evcc-profile-chip-text","Profile Chip Text"),ee.color("--evcc-room-chip-bg","Room Chip BG"),ee.color("--evcc-room-chip-border","Room Chip Border"),ee.color("--evcc-room-chip-text","Room Chip Text"),ee.number("--evcc-room-fill-opacity","Room Fill Opacity"),ee.size("--evcc-room-grid-columns","Room Grid Columns"),ee.size("--evcc-room-grid-gap","Room Grid Gap"),ee.size("--evcc-room-grid-min","Room Grid Min")];var Te=q("Floor Textures","number"),he=q("Floor Textures \u2014 Tile","color"),ye=q("Floor Textures \u2014 Wood","color"),fe=q("Floor Textures \u2014 Marble","color"),Re=q("Floor Textures \u2014 Concrete","color"),$e=q("Floor Textures \u2014 Carpet Low","color"),Me=q("Floor Textures \u2014 Carpet High","color"),Ie=q("Floor Textures \u2014 Granite","color"),lr=[Te.number("--evcc-floor-textures-card-enabled","Card Textures Enabled (0/1)"),Te.number("--evcc-floor-textures-map-enabled","Map Textures Enabled (0/1)"),Te.number("--evcc-floor-texture-opacity-card","Card Texture Opacity (all)"),Te.number("--evcc-floor-texture-opacity-map","Map Texture Opacity (all)"),he.color("--evcc-floor-tile-base","Tile Base Color"),he.color("--evcc-floor-tile-grout","Tile Grout Color"),he.color("--evcc-floor-tile-accent","Tile Accent Color"),he.number("--evcc-floor-tile-opacity-card","Tile Card Opacity"),he.number("--evcc-floor-tile-face-opacity","Tile Face Layer Opacity"),he.number("--evcc-floor-tile-grout-opacity","Tile Grout Layer Opacity"),he.number("--evcc-floor-tile-line-opacity","Tile Grout Line Layer Opacity"),ye.color("--evcc-floor-wood-base","Wood Base Color"),ye.color("--evcc-floor-wood-accent","Wood Accent Color"),ye.number("--evcc-floor-wood-opacity-card","Wood Card Opacity"),ye.number("--evcc-floor-wood-depth-opacity","Wood Depth Layer Opacity"),ye.number("--evcc-floor-wood-grain-opacity","Wood Grain Layer Opacity"),ye.number("--evcc-floor-wood-seam-opacity","Wood Seam Layer Opacity"),fe.color("--evcc-floor-marble-base","Marble Base Color"),fe.color("--evcc-floor-marble-micro","Marble Micro Color"),fe.color("--evcc-floor-marble-accent","Marble Accent Color"),fe.number("--evcc-floor-marble-opacity-card","Marble Card Opacity"),fe.number("--evcc-floor-marble-base-opacity","Marble Base Layer Opacity"),fe.number("--evcc-floor-marble-micro-opacity","Marble Micro Layer Opacity"),fe.number("--evcc-floor-marble-vein-opacity","Marble Vein Layer Opacity"),Re.color("--evcc-floor-concrete-base","Concrete Base Color"),Re.color("--evcc-floor-concrete-accent","Concrete Accent Color"),Re.number("--evcc-floor-concrete-opacity-card","Concrete Card Opacity"),Re.number("--evcc-floor-concrete-broad-opacity","Concrete Broad Layer Opacity"),Re.number("--evcc-floor-concrete-micro-opacity","Concrete Micro Layer Opacity"),$e.color("--evcc-floor-carpet-low-base","Carpet Low Base Color"),$e.color("--evcc-floor-carpet-low-accent","Carpet Low Accent Color"),$e.number("--evcc-floor-carpet-low-opacity-card","Carpet Low Card Opacity"),$e.number("--evcc-floor-carpet-low-texture-opacity","Carpet Low Texture Layer Opacity"),Me.color("--evcc-floor-carpet-high-base","Carpet High Base Color"),Me.color("--evcc-floor-carpet-high-accent","Carpet High Accent Color"),Me.number("--evcc-floor-carpet-high-opacity-card","Carpet High Card Opacity"),Me.number("--evcc-floor-carpet-high-texture-opacity","Carpet High Texture Layer Opacity"),Ie.color("--evcc-floor-granite-light-base","Granite Base Color"),Ie.color("--evcc-floor-granite-light-accent","Granite Accent Color"),Ie.number("--evcc-floor-granite-light-opacity-card","Granite Card Opacity"),Ie.number("--evcc-floor-granite-light-texture-opacity","Granite Texture Layer Opacity")];var dr=[E.number("--evcc-drag-opacity","Drag Opacity"),E.number("--evcc-drag-scale","Drag Scale"),E.shadow("--evcc-drag-shadow","Drag Shadow"),E.color("--evcc-order-chip-bg","Order Chip BG"),E.color("--evcc-order-chip-border","Order Chip Border"),E.color("--evcc-order-chip-text","Order Chip Text"),E.color("--evcc-order-feedback-border","Order Feedback Border"),E.color("--evcc-order-target-outline","Order Target Outline"),E.text("--evcc-progress-complete","Progress Complete"),E.color("--evcc-progress-fill","Progress Fill"),E.color("--evcc-queue-chip-bg","Queue Chip BG"),E.color("--evcc-queue-chip-border","Queue Chip Border"),E.size("--evcc-queue-chip-gap","Queue Chip Gap"),E.color("--evcc-queue-chip-text","Queue Chip Text"),E.color("--evcc-queue-completed-bg","Queue Completed BG"),E.color("--evcc-queue-completed-border","Queue Completed Border"),E.number("--evcc-queue-completed-opacity","Queue Completed Opacity"),E.color("--evcc-queue-completed-text","Queue Completed Text"),E.color("--evcc-queue-current-bg","Queue Current BG"),E.color("--evcc-queue-current-border","Queue Current Border"),E.shadow("--evcc-queue-current-glow","Queue Current Glow"),E.color("--evcc-queue-current-text","Queue Current Text"),E.color("--evcc-queue-hover-bg","Queue Hover BG"),E.color("--evcc-queue-hover-border","Queue Hover Border"),E.color("--evcc-queue-hover-text","Queue Hover Text"),E.color("--evcc-queue-inferred-bg","Queue Inferred BG"),E.color("--evcc-queue-inferred-border","Queue Inferred Border"),E.shadow("--evcc-queue-inferred-glow","Queue Inferred Glow"),E.color("--evcc-queue-inferred-text","Queue Inferred Text"),E.color("--evcc-queue-order-bg","Queue Order BG"),E.color("--evcc-queue-order-border","Queue Order Border"),E.color("--evcc-queue-order-text","Queue Order Text"),E.color("--evcc-queue-pending-bg","Queue Pending BG"),E.color("--evcc-queue-pending-border","Queue Pending Border"),E.number("--evcc-queue-pending-opacity","Queue Pending Opacity"),E.color("--evcc-queue-pending-text","Queue Pending Text"),E.color("--evcc-queue-skipped-bg","Queue Skipped BG"),E.color("--evcc-queue-skipped-border","Queue Skipped Border"),E.color("--evcc-queue-skipped-text","Queue Skipped Text"),E.duration("--evcc-reorder-feedback-duration","Reorder Feedback Duration"),E.easing("--evcc-reorder-flip-easing","Reorder Flip Easing")];var ur=[T.color("--evcc-color-cleaning","Color Cleaning"),T.color("--evcc-color-docked","Color Docked"),T.color("--evcc-color-error","Color Error"),T.color("--evcc-color-idle","Color Idle"),T.color("--evcc-color-paused","Color Paused"),T.color("--evcc-color-returning","Color Returning"),T.color("--evcc-conf-high","Conf High"),T.color("--evcc-conf-low","Conf Low"),T.color("--evcc-conf-mid","Conf Mid"),T.color("--evcc-conf-none","Conf None"),T.color("--evcc-confidence-high-bg","Confidence High BG"),T.color("--evcc-confidence-high-border","Confidence High Border"),T.color("--evcc-confidence-high-text","Confidence High Text"),T.color("--evcc-confidence-low-bg","Confidence Low BG"),T.color("--evcc-confidence-low-border","Confidence Low Border"),T.color("--evcc-confidence-low-text","Confidence Low Text"),T.color("--evcc-confidence-medium-bg","Confidence Medium BG"),T.color("--evcc-confidence-medium-border","Confidence Medium Border"),T.color("--evcc-confidence-medium-text","Confidence Medium Text"),T.color("--evcc-sem-error","Sem Error"),T.color("--evcc-sem-info","Sem Info"),T.color("--evcc-sem-success","Sem Success"),T.color("--evcc-sem-warning","Sem Warning"),T.color("--evcc-status-cleaning-bg","Status Cleaning BG"),T.color("--evcc-status-cleaning-border","Status Cleaning Border"),T.color("--evcc-status-cleaning-text","Status Cleaning Text"),T.color("--evcc-status-dot-charging","Status Dot Charging"),T.color("--evcc-status-dot-cleaning","Status Dot Cleaning"),T.color("--evcc-status-dot-docked","Status Dot Docked"),T.color("--evcc-status-dot-error","Status Dot Error"),T.color("--evcc-status-dot-idle","Status Dot Idle"),T.color("--evcc-status-dot-offline","Status Dot Offline"),T.color("--evcc-status-dot-paused","Status Dot Paused"),T.color("--evcc-status-dot-returning","Status Dot Returning"),T.shadow("--evcc-status-dot-shadow","Status Dot Shadow"),T.color("--evcc-status-dot-unavailable","Status Dot Unavailable"),T.duration("--evcc-status-pulse-duration","Status Pulse Duration")];var mr=[k.color("--evcc-estimate-default-bg","Estimate Default BG"),k.color("--evcc-estimate-default-border","Estimate Default Border"),k.color("--evcc-estimate-default-text","Estimate Default Text"),k.color("--evcc-estimate-learned-bg","Estimate Learned BG"),k.color("--evcc-estimate-learned-border","Estimate Learned Border"),k.color("--evcc-estimate-learned-text","Estimate Learned Text"),k.duration("--evcc-learning-anim-duration-fast","Learning Anim Duration Fast"),k.duration("--evcc-learning-anim-duration-normal","Learning Anim Duration Normal"),k.duration("--evcc-learning-anim-duration-slow","Learning Anim Duration Slow"),k.text("--evcc-learning-anim-ease","Learning Anim Ease"),k.size("--evcc-learning-chip-font-size","Learning Chip Font Size"),k.typography("--evcc-learning-chip-font-weight","Learning Chip Font Weight"),k.size("--evcc-learning-chip-radius","Learning Chip Radius"),k.color("--evcc-learning-confidence-high-bg","Learning Confidence High BG"),k.color("--evcc-learning-confidence-high-border","Learning Confidence High Border"),k.text("--evcc-learning-confidence-high-gradient","Learning Confidence High Gradient"),k.color("--evcc-learning-confidence-high-text","Learning Confidence High Text"),k.color("--evcc-learning-confidence-low-bg","Learning Confidence Low BG"),k.color("--evcc-learning-confidence-low-border","Learning Confidence Low Border"),k.text("--evcc-learning-confidence-low-gradient","Learning Confidence Low Gradient"),k.color("--evcc-learning-confidence-low-text","Learning Confidence Low Text"),k.color("--evcc-learning-confidence-medium-bg","Learning Confidence Medium BG"),k.color("--evcc-learning-confidence-medium-border","Learning Confidence Medium Border"),k.text("--evcc-learning-confidence-medium-gradient","Learning Confidence Medium Gradient"),k.color("--evcc-learning-confidence-medium-text","Learning Confidence Medium Text"),k.color("--evcc-learning-confidence-neutral-bg","Learning Confidence Neutral BG"),k.color("--evcc-learning-confidence-neutral-border","Learning Confidence Neutral Border"),k.text("--evcc-learning-confidence-neutral-gradient","Learning Confidence Neutral Gradient"),k.color("--evcc-learning-confidence-neutral-text","Learning Confidence Neutral Text"),k.shadow("--evcc-learning-current-glow","Learning Current Glow"),k.color("--evcc-learning-note-text","Learning Note Text"),k.color("--evcc-learning-panel-bg","Learning Panel BG"),k.color("--evcc-learning-panel-border","Learning Panel Border"),k.shadow("--evcc-learning-panel-shadow","Learning Panel Shadow"),k.color("--evcc-learning-reanchor-border","Learning Reanchor Border"),k.color("--evcc-learning-reanchor-highlight","Learning Reanchor Highlight"),k.color("--evcc-learning-text-muted","Learning Text Muted"),k.color("--evcc-learning-text-primary","Learning Text Primary"),k.color("--evcc-learning-text-secondary","Learning Text Secondary"),k.color("--evcc-learning-warning-text","Learning Warning Text")];var vr=[$.color("--evcc-modal-accent","Modal Accent"),$.color("--evcc-modal-accent-bg","Modal Accent BG"),$.color("--evcc-modal-accent-border","Modal Accent Border"),$.color("--evcc-modal-accent-text","Modal Accent Text"),$.color("--evcc-modal-backdrop-bg","Modal Backdrop BG"),$.number("--evcc-modal-backdrop-blur","Modal Backdrop Blur"),$.color("--evcc-modal-bg","Modal BG"),$.color("--evcc-modal-border","Modal Border"),$.color("--evcc-modal-border-default","Modal Border Default"),$.color("--evcc-modal-border-strong","Modal Border Strong"),$.color("--evcc-modal-border-subtle","Modal Border Subtle"),$.color("--evcc-modal-chip-active-bg","Modal Chip Active BG"),$.color("--evcc-modal-chip-active-border","Modal Chip Active Border"),$.color("--evcc-modal-chip-active-text","Modal Chip Active Text"),$.color("--evcc-modal-chip-bg","Modal Chip BG"),$.color("--evcc-modal-chip-border","Modal Chip Border"),$.color("--evcc-modal-chip-hover-bg","Modal Chip Hover BG"),$.color("--evcc-modal-chip-hover-border","Modal Chip Hover Border"),$.color("--evcc-modal-chip-hover-text","Modal Chip Hover Text"),$.color("--evcc-modal-chip-text","Modal Chip Text"),$.color("--evcc-modal-footer-bg","Modal Footer BG"),$.color("--evcc-modal-header-bg","Modal Header BG"),$.color("--evcc-modal-input-bg","Modal Input BG"),$.size("--evcc-modal-padding","Modal Padding"),$.size("--evcc-modal-radius","Modal Radius"),$.size("--evcc-modal-section-gap","Modal Section Gap"),$.shadow("--evcc-modal-shadow","Modal Shadow"),$.color("--evcc-modal-surface-input","Modal Surface Input"),$.color("--evcc-modal-surface-panel","Modal Surface Panel"),$.color("--evcc-modal-surface-section","Modal Surface Section"),$.color("--evcc-modal-text-muted","Modal Text Muted"),$.color("--evcc-modal-text-primary","Modal Text Primary"),$.color("--evcc-modal-text-secondary","Modal Text Secondary"),$.color("--evcc-modal-warning-bg","Modal Warning BG"),$.color("--evcc-modal-warning-border","Modal Warning Border"),$.color("--evcc-modal-warning-text","Modal Warning Text")];var pr=[Y.typography("--evcc-font-family","Font Family"),Y.size("--evcc-gap","Gap"),Y.size("--evcc-grid-gap","Grid Gap"),Y.motion("--evcc-hover-lift","Hover Lift"),Y.size("--evcc-pad","Pad"),Y.number("--evcc-press-scale","Press Scale"),Y.size("--evcc-radius-card","Radius Card"),Y.size("--evcc-radius-chip","Radius Chip"),Y.size("--evcc-radius-inner","Radius Inner"),Y.size("--evcc-radius-panel","Radius Panel"),Y.size("--evcc-section-gap","Section Gap"),Y.text("--evcc-space-lg","Space Lg"),Y.text("--evcc-space-md","Space Md"),Y.text("--evcc-space-sm","Space Sm"),Y.motion("--evcc-transition-normal","Transition Normal")];var si=[ir,nr,cr,sr,or,lr,dr,ur,mr,vr,pr];function oi(i){let e=new Set;for(let t of i){let r=String(t?.key??"");if(!r)throw new Error("[theme-tokens] Registry entry is missing key.");if(e.has(r))throw new Error(`[theme-tokens] Duplicate token key detected: ${r}`);e.add(r)}}var re=si.flat();oi(re);var ge=Object.freeze(Object.fromEntries(re.map(i=>[i.key,i]))),tc=Object.freeze(K.reduce((i,e)=>(i[e]=re.filter(t=>t.group===e),i),{}));function li(i,e){let t=String(i||"").trim(),r;if(/^#[0-9a-fA-F]{8}$/.test(t))r=`#${t.slice(1,7)}`;else if(/^#[0-9a-fA-F]{6}$/.test(t))r=t;else return t;if(e==null)return t;let a=Math.max(0,Math.min(1,Number(e)));if(Number.isNaN(a))return t;let n=Math.round(a*255).toString(16).padStart(2,"0").toLowerCase();return`${r}${n}`}function hr(i){i._emptyThemeDraft=function(){return{tokens:{},colors:{},alpha:{}}},i._themeDraftHasOverrides=function(e){return Object.keys(e.tokens).length>0||Object.keys(e.colors).length>0||Object.keys(e.alpha).length>0},i._applyThemeDraftBucket=function(e,t){!t||typeof t!="object"||Object.entries(t).forEach(([r,a])=>{if(a==null||a===""){delete e[r];return}e[r]=a})},i._normalizeThemeDraft=function(e){let t=this._emptyThemeDraft();return!e||typeof e!="object"||(this._applyThemeDraftBucket(t.tokens,e.tokens),this._applyThemeDraftBucket(t.colors,e.colors),this._applyThemeDraftBucket(t.alpha,e.alpha)),t},i.applyThemeDraftPatch=function(e){let t=this._ensureThemeState();this._applyThemeDraftBucket(t.workingDraft.tokens,e?.tokens),this._applyThemeDraftBucket(t.workingDraft.colors,e?.colors),this._applyThemeDraftBucket(t.workingDraft.alpha,e?.alpha),t.draftDirty=this._themeDraftHasOverrides(t.workingDraft)},i.applyThemeActivation=function(e,t={}){let r=this._ensureThemeState(),a=t.clearDraft!==!1;r.activeThemeId=e??null,a&&(r.workingDraft=this._emptyThemeDraft(),r.draftDirty=!1)},i._ensureThemeState=function(){return this._themeState||(this._themeState={library:{},librarySummary:[],defaultThemeId:null,activeThemeId:null,workingDraft:this._emptyThemeDraft(),draftDirty:!1,editorMode:"live",selectedThemeId:null,activeSubTab:"presets",focusedGroup:"",tokenSearchQuery:"",selectedGroupFilter:"all",groupOpen:{},groupSearchQueryByName:{},modifiedOnly:!1}),this._themeState},i.setBackendThemeState=function(e){let t=this._ensureThemeState();t.activeThemeId=e?.active_theme_id??null,t.workingDraft=this._normalizeThemeDraft(e?.working_draft),t.draftDirty=e?.draft_dirty??this._themeDraftHasOverrides(t.workingDraft),t.editorMode=e?.editor_mode??"live"},i.setThemeLibrary=function(e){let t=this._ensureThemeState();t.library=e?.library??{},t.librarySummary=e?.themes??[],t.defaultThemeId=e?.default_theme_id??null},i.resolvedTheme=function(){let e=this._ensureThemeState(),t={},r={},a={},n={},c=e.library?.[e.activeThemeId]||null;return c&&(Object.entries(c.colors||{}).forEach(([s,o])=>{a[s]=o,r[s]="theme"}),Object.entries(c.alpha||{}).forEach(([s,o])=>{n[s]=o,r[s]||(r[s]="theme")}),Object.entries(c.tokens||{}).forEach(([s,o])=>{t[s]=o,r[s]="theme"})),Object.entries(e.workingDraft.colors).forEach(([s,o])=>{a[s]=o,r[s]="draft"}),Object.entries(e.workingDraft.alpha).forEach(([s,o])=>{n[s]=o,r[s]="draft"}),Object.entries(e.workingDraft.tokens).forEach(([s,o])=>{t[s]=o,r[s]="draft"}),Object.entries(a).forEach(([s,o])=>{let l=s in n?n[s]:null;t[s]=li(o,l)}),{tokens:t,sources:r}},i.setThemeSubTab=function(e){this._ensureThemeState().activeSubTab=e},i.setThemeSearchQuery=function(e){this._ensureThemeState().tokenSearchQuery=String(e||"").toLowerCase()},i.setThemeModifiedOnly=function(e){this._ensureThemeState().modifiedOnly=!!e},i.setSelectedTheme=function(e){this._ensureThemeState().selectedThemeId=e},i.setThemeFocusedGroup=function(e){let t=this._ensureThemeState(),r=String(e||"").trim();t.focusedGroup=K.includes(r)?r:""},i.getThemeFocusedGroup=function(){let e=String(this._ensureThemeState().focusedGroup||"").trim();return K.includes(e)?e:""},i.currentThemePreviewGroup=function(){let e=this._ensureThemeState(),t=String(e.selectedGroupFilter||"").trim(),r=String(e.activeSubTab||"presets").trim().toLowerCase();if(K.includes(t))return t;let a=this.getThemeFocusedGroup();if(K.includes(a))return a;if(r==="palette")return"Shared Foundations";let n=K.find(c=>this.isThemeGroupOpen(c));return n||"Shared Foundations"},i.setThemeGroupFilter=function(e){let t=this._ensureThemeState();t.selectedGroupFilter=String(e||"all")},i.toggleThemeGroup=function(e){let t=this._ensureThemeState();t.groupOpen[e]=!this.isThemeGroupOpen(e)},i.isThemeGroupOpen=function(e){let t=this._ensureThemeState();return e in t.groupOpen?!!t.groupOpen[e]:!0},i.setThemeGroupSearchQuery=function(e,t){let r=this._ensureThemeState();r.groupSearchQueryByName[e]=String(t||"").toLowerCase()},i.getThemeGroupSearchQuery=function(e){return this._ensureThemeState().groupSearchQueryByName[e]||""},i.getSelectedTheme=function(){let e=this._ensureThemeState();return e.library?.[e.selectedThemeId]||null},i.getActiveTheme=function(){let e=this._ensureThemeState();return e.library?.[e.activeThemeId]||null},i.getThemeGroupFilter=function(){return this._ensureThemeState().selectedGroupFilter||"all"},i.tokenMatchesGlobalThemeSearch=function(e,t="",r=""){let a=String(r||"").toLowerCase();if(!a)return!0;let n=String(e?.label||"").toLowerCase(),c=String(e?.key||"").toLowerCase(),s=String(t||"").toLowerCase(),o=Array.isArray(e?.aliases)?e.aliases.map(u=>String(u||"").toLowerCase()):[],l=Array.isArray(e?.usage)?e.usage.map(u=>String(u||"").toLowerCase()):[],d=Array.isArray(e?.affects)?e.affects.map(u=>String(u||"").toLowerCase()):[];return!!(n.includes(a)||c.includes(a)||s.includes(a)||o.some(u=>u.includes(a))||l.some(u=>u.includes(a))||d.some(u=>u.includes(a)))},i.tokenMatchesThemeGroupSearch=function(e,t="",r){let a=this.getThemeGroupSearchQuery(r);return this.tokenMatchesGlobalThemeSearch(e,t,a)},i.filteredThemeTokens=function(e,t={}){let r=this._ensureThemeState(),{tokens:a,sources:n}=this.resolvedTheme(),c=r.tokenSearchQuery,s=r.modifiedOnly,o=r.selectedGroupFilter||"all",l=t.excludeKeys instanceof Set?t.excludeKeys:new Set;return e.filter(d=>{let u=d.key,v=a[u]||"",m=n[u]||"ha",p=d.group||"";if(l.has(u)||s&&m!=="draft")return!1;if(o==="modified"){if(m!=="draft")return!1}else if(o!=="all"&&p!==o&&!p.startsWith(o+" \u2014 "))return!1;return!!this.tokenMatchesGlobalThemeSearch(d,v,c)})},i.filteredThemeTokensForGroup=function(e,t,r={}){let{tokens:a}=this.resolvedTheme();return this.filteredThemeTokens(t,r).filter(n=>{if(n.group!==e)return!1;let c=a[n.key]||"";return this.tokenMatchesThemeGroupSearch(n,c,e)})},i.themeGroupCounts=function(e,t,r={}){let{sources:a}=this.resolvedTheme(),n=this.filteredThemeTokensForGroup(e,t,r),c=n.length;return{modified:n.filter(o=>(a[o.key]||"ha")==="draft").length,total:c}},i.shouldForceThemeGroupOpenForSearch=function(e,t,r={}){return this._ensureThemeState().tokenSearchQuery?this.themeGroupCounts(e,t,r).total>0:!1}}function fr(i){i._mapViewActive=null,i._mapSegmentsData=null,i._selectedSegmentIds=null,i._mapViewStorageKey=function(){return`evcc_map_view_active_${Z(this.config?.vacuum??"")}`},i.isMapViewActive=function(){if(this._mapViewActive===null){let e=localStorage.getItem(this._mapViewStorageKey());this._mapViewActive=e==="true"}return this._mapViewActive},i.setMapViewActive=function(e){this._mapViewActive=!!e;try{localStorage.setItem(this._mapViewStorageKey(),String(this._mapViewActive))}catch{}},i.toggleMapView=function(){this.setMapViewActive(!this.isMapViewActive())},i.mapSegmentsData=function(){return this._mapSegmentsData},i.setMapSegmentsData=function(e){let t=this._mapSegmentsData?.map_id;this._mapSegmentsData=e,e?.map_id!==t?(this._segmentRoomOverlay=null,this._dotAnchorOverlay=null,this._mapAnchorMode=!1,this.resetMapTransform()):(this._segmentRoomOverlay=null,this._dotAnchorOverlay=null),e?.map_id&&(this._migrateLegacySegmentRoomLinks(),this._migrateLegacyDotAnchors())},i.mapSegments=function(){return this._mapSegmentsData?.segments??[]},i.mapImageUrl=function(){let e=this._mapSegmentsData?.image_variants??{};return(e.dark??e.default??e.light)?.browser_url??null},i._getSegmentIds=function(){return this._selectedSegmentIds||(this._selectedSegmentIds=new Set),this._selectedSegmentIds},i.selectedSegmentIds=function(){return this._getSegmentIds()},i.isSegmentSelected=function(e){return this._getSegmentIds().has(String(e))},i.toggleSegmentSelected=function(e){let t=this._getSegmentIds(),r=String(e);t.has(r)?t.delete(r):t.add(r)},i.clearSegmentSelection=function(){this._getSegmentIds().clear()},i.enableSegmentForRoom=function(e){let t=this.segmentIdForRoom(e);t&&this._getSegmentIds().add(String(t))},i.disableSegmentForRoom=function(e){let t=this.segmentIdForRoom(e);t&&this._getSegmentIds().delete(String(t))},i.selectedSegments=function(){let e=this.mapSegments(),t=[];for(let r of this._getSegmentIds()){let a=e.find(n=>String(n.segment_id)===r);a&&t.push(a)}return t},i._configSelectedSegmentId=null,i.configSelectedSegmentId=function(){return this._configSelectedSegmentId},i.setConfigSelectedSegmentId=function(e){this._configSelectedSegmentId=e!=null?String(e):null},i._segmentRoomOverlay=null,i._segRoomLegacyKey=function(){let e=this._mapSegmentsData?.map_id??"unknown";return`evcc_seg_rooms_${Z(this.config?.vacuum??"")}_${e}`},i._ensureSegmentRoomOverlay=function(){return this._segmentRoomOverlay||(this._segmentRoomOverlay=new Map),this._segmentRoomOverlay},i._migrateLegacySegmentRoomLinks=function(){let e;try{e=localStorage.getItem(this._segRoomLegacyKey())}catch{return}if(!e)return;let t;try{t=JSON.parse(e)}catch{return}if(!t||typeof t!="object")return;let r=new Set;for(let c of this._mapSegmentsData?.segments||[])c&&c.room_id!=null&&r.add(String(c.segment_id));let a=this._mapSegmentsData?.map_id;if(!a)return;let n=0;for(let[c,s]of Object.entries(t))if(!r.has(String(c)))try{this.card?.setSegmentRoomLink?.(a,c,s),n+=1}catch{}try{localStorage.removeItem(this._segRoomLegacyKey())}catch{}n>0&&console?.info&&console.info(`[evcc] Migrated ${n} segment-room link(s) from localStorage to backend.`)},i.roomIdForSegment=function(e){let t=String(e),r=this.mapSegments().find(a=>String(a.segment_id)===t);return r?.room_id!=null?String(r.room_id):this._segmentRoomOverlay?.get(t)??null},i.segmentIdForRoom=function(e){let t=String(e),r=this.mapSegments().find(a=>a.room_id!=null&&String(a.room_id)===t);if(r)return String(r.segment_id);if(this._segmentRoomOverlay){for(let[a,n]of this._segmentRoomOverlay)if(n===t)return a}return null},i.assignSegmentRoom=function(e,t){let r=String(e),a=String(t),n=this._ensureSegmentRoomOverlay();for(let[s,o]of n)o===a&&s!==r&&n.delete(s);n.set(r,a);let c=this._mapSegmentsData?.map_id;if(c)try{this.card?.setSegmentRoomLink?.(c,r,a)}catch{}},i.unassignSegmentRoom=function(e){let t=String(e);this._ensureSegmentRoomOverlay().delete(t);let r=this._mapSegmentsData?.map_id;if(r)try{this.card?.setSegmentRoomLink?.(r,t,null)}catch{}},i.configSelectedSegment=function(){let e=this._configSelectedSegmentId;return e?this.mapSegments().find(t=>String(t.segment_id)===e)??null:null},i._mapActionStatus=null,i.mapActionStatus=function(){return this._mapActionStatus},i.setMapActionStatus=function(e){this._mapActionStatus=e},i.clearMapActionStatus=function(){this._mapActionStatus=null},i.mapNudgeStep=function(){let e=this._mapSegmentsData?.image_variants??{},t=e.dark??e.default??e.light,r=t?.width??1e3,a=t?.height??1e3;return{x:Math.max(1,Math.round(r*.005)),y:Math.max(1,Math.round(a*.005))}},i._mapZoom=1,i._mapTranslateX=0,i._mapTranslateY=0,i.mapZoom=function(){return this._mapZoom},i.mapTranslateX=function(){return this._mapTranslateX},i.mapTranslateY=function(){return this._mapTranslateY},i.resetMapTransform=function(){this._mapZoom=1,this._mapTranslateX=0,this._mapTranslateY=0},i.applyMapZoom=function(e,t,r){let a=Math.max(.5,Math.min(8,e)),n=a/this._mapZoom;this._mapTranslateX=t-(t-this._mapTranslateX)*n,this._mapTranslateY=r-(r-this._mapTranslateY)*n,this._mapZoom=a},i.applyMapPan=function(e,t){this._mapTranslateX+=e,this._mapTranslateY+=t},i._dotAnchorOverlay=null,i._mapAnchorMode=!1,i._dotAnchorLegacyKey=function(){let e=this._mapSegmentsData?.map_id??"unknown";return`evcc_dot_anchors_${Z(this.config?.vacuum??"")}_${e}`},i._ensureDotAnchorOverlay=function(){return this._dotAnchorOverlay||(this._dotAnchorOverlay=new Map),this._dotAnchorOverlay},i._migrateLegacyDotAnchors=function(){let e;try{e=localStorage.getItem(this._dotAnchorLegacyKey())}catch{return}if(!e)return;let t;try{t=JSON.parse(e)}catch{return}if(!t||typeof t!="object")return;let r=this._mapSegmentsData?.companion_anchors||{},a=this._mapSegmentsData?.map_id;if(!a)return;let n=0;for(let[c,s]of Object.entries(t)){if(r[c])continue;let o=s?.pct_x,l=s?.pct_y;if(!(o==null||l==null))try{this.card?.setCompanionAnchor?.(a,c,o,l),n+=1}catch{}}try{localStorage.removeItem(this._dotAnchorLegacyKey())}catch{}n>0&&console?.info&&console.info(`[evcc] Migrated ${n} companion anchor(s) from localStorage to backend.`)},i.roomDotAnchor=function(e){let t=String(e);return this._dotAnchorOverlay?.has(t)?this._dotAnchorOverlay.get(t):this._mapSegmentsData?.companion_anchors?.[t]??null},i.setRoomDotAnchor=function(e,t,r){let a=String(e);this._ensureDotAnchorOverlay().set(a,{pct_x:t,pct_y:r});let n=this._mapSegmentsData?.map_id;if(n)try{this.card?.setCompanionAnchor?.(n,a,t,r)}catch{}},i.isMapAnchorMode=function(){return this._mapAnchorMode},i.setMapAnchorMode=function(e){this._mapAnchorMode=!!e},i.currentMapRoom=function(){let e=this.rawRobotPosition?.();if(!e||e.x==null||e.y==null)return null;let t=this.getRoomsForActiveMap?.()??[],r=50;for(let a of t){if(a.is_transition||a.isTransition)continue;let n=a.bounds;if(n&&e.x>=n.min_x-r&&e.x<=n.max_x+r&&e.y>=n.min_y-r&&e.y<=n.max_y+r)return a}return null},i._configSelectedVertexIndex=null,i.configSelectedVertexIndex=function(){return this._configSelectedVertexIndex},i.setConfigSelectedVertexIndex=function(e){this._configSelectedVertexIndex=e!=null?Number(e):null},i._mapAnimalSelection=null,i._animalSelectionKey=function(){return`evcc_animal_${Z(this.config?.vacuum??"")}`},i.mapAnimalSelection=function(){if(this._mapAnimalSelection===null)try{this._mapAnimalSelection=localStorage.getItem(this._animalSelectionKey())??"cat"}catch{this._mapAnimalSelection="cat"}return this._mapAnimalSelection},i.setMapAnimalSelection=function(e){this._mapAnimalSelection=e;try{localStorage.setItem(this._animalSelectionKey(),e)}catch{}},i._mapAnimalScale=null,i._animalScaleKey=function(){return`evcc_animal_scale_${Z(this.config?.vacuum??"")}`},i.mapAnimalScale=function(){if(this._mapAnimalScale===null)try{let e=parseFloat(localStorage.getItem(this._animalScaleKey()));this._mapAnimalScale=isFinite(e)?e:1}catch{this._mapAnimalScale=1}return this._mapAnimalScale},i.setMapAnimalScale=function(e){let t=Math.max(.5,Math.min(3,Number(e)));this._mapAnimalScale=t;try{localStorage.setItem(this._animalScaleKey(),String(t))}catch{}}}function gr(i){i._ensureLearningState=function(){return this._learning||(this._learning={estimate:null,reanchored:null,completedRooms:[],nextRoom:null,jobActive:!1,summary:null,dashboardSnapshot:null,incompleteRunLog:null,troubleRoomsLog:null,roomEstimates:{},roomEstimateMeta:{stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}}),Array.isArray(this._learning.completedRooms)||(this._learning.completedRooms=[]),(!this._learning.roomEstimates||typeof this._learning.roomEstimates!="object")&&(this._learning.roomEstimates={}),(!this._learning.roomEstimateMeta||typeof this._learning.roomEstimateMeta!="object")&&(this._learning.roomEstimateMeta={stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}),this._learning},i.clearLearningState=function(){this._learning={estimate:null,reanchored:null,completedRooms:[],nextRoom:null,jobActive:!1,summary:null,dashboardSnapshot:null,incompleteRunLog:null,troubleRoomsLog:null,roomEstimates:{},roomEstimateMeta:{stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}}},i.clearLearningJobContext=function(){let e=this._ensureLearningState();e.estimate=null,e.reanchored=null,e.completedRooms=[],e.nextRoom=null,e.jobActive=!1,e.summary=null},i.learningState=function(){return this._ensureLearningState()},i.dashboardSnapshot=function(){return this._ensureLearningState().dashboardSnapshot??null},i.dashboardJobProgress=function(){return this.dashboardSnapshot()?.job_progress??null},i.dashboardJobControl=function(){return this.dashboardSnapshot()?.job_control??null},i.dashboardStartStatus=function(){return this.dashboardSnapshot()?.start_status??null},i.dashboardLifecycle=function(){return this.dashboardSnapshot()?.lifecycle??null},i.dashboardUpkeep=function(){return this.dashboardSnapshot()?.upkeep??null},i.dashboardStatusSummary=function(){return this.dashboardSnapshot()?.status_summary??null},i.dashboardAttentionSummary=function(){return this.dashboardSnapshot()?.attention_summary??null},i.dashboardPlannedJobEstimate=function(){return this.dashboardSnapshot()?.planned_job_estimate??null},i.dashboardPlannedWaterEstimate=function(){return this.dashboardPlannedJobEstimate()?.water_estimate??null},i.dashboardPlannedWaterRooms=function(){let e=this.dashboardPlannedWaterEstimate()?.rooms;return Array.isArray(e)?e:[]},i.dashboardPlannedWaterRoomForRoom=function(e,t=null){let r=e==null?null:String(e),a=t==null?null:String(t).trim().toLowerCase();return this.dashboardPlannedWaterRooms().find(n=>{let c=n?.room_id==null?null:String(n.room_id),s=n?.slug==null?null:String(n.slug).trim().toLowerCase();return!!(r!=null&&c===r||a&&s===a)})??null},i.dashboardPlannedJobEstimateAvailable=function(){return!!this.dashboardPlannedJobEstimate()?.available},i.dashboardPlannedJobEstimateTotalMinutes=function(){let e=Number(this.dashboardPlannedJobEstimate()?.total_minutes);return Number.isFinite(e)?e:null},i.dashboardJobProgressTimeline=function(){let e=this.dashboardJobProgress()?.timeline;return Array.isArray(e)?e:[]},i._dashboardJobIsActive=function(){let e=this.dashboardJobProgress();if(!e||typeof e!="object")return!1;if(typeof e.terminal=="boolean")return!e.terminal;let t=String(e.status??"").trim().toLowerCase();return t?!["complete","completed","finished","idle","terminal","not_started","inactive"].includes(t):!1},i.incompleteRunLog=function(){return this._ensureLearningState().incompleteRunLog??null},i.hasIncompleteRunLog=function(){let e=this.incompleteRunLog();if(!e)return!1;let t=e.missed_room_ids;return Array.isArray(t)&&t.length>0},i.incompleteRunMissedRoomIds=function(){let e=this.incompleteRunLog()?.missed_room_ids;return Array.isArray(e)?e:[]},i.incompleteRunMissedRooms=function(){let e=this.incompleteRunLog()?.missed_rooms;return Array.isArray(e)?e:[]},i.setIncompleteRunLog=function(e){let t=this._ensureLearningState();t.incompleteRunLog=e??null},i.clearIncompleteRunLog=function(){let e=this._ensureLearningState();e.incompleteRunLog=null},i.troubleRoomsLog=function(){return this._ensureLearningState().troubleRoomsLog??null},i.hasTroubleRooms=function(){let e=this.troubleRoomsLog();if(!e||typeof e!="object")return!1;let t=e.rooms;return!t||typeof t!="object"?!1:Object.values(t).some(r=>r?.is_trouble===!0)},i.troubleRoomForRoom=function(e){let t=this.troubleRoomsLog();if(!t||typeof t!="object")return null;let r=t.rooms;if(!r||typeof r!="object")return null;let a=String(e);return r[a]??null},i.setTroubleRoomsLog=function(e){let t=this._ensureLearningState();t.troubleRoomsLog=e??null},i.clearTroubleRoomsLog=function(){let e=this._ensureLearningState();e.troubleRoomsLog=null},i.learningEstimate=function(){return this._ensureLearningState().estimate??this.dashboardPlannedJobEstimate()??null},i.learningReanchored=function(){return this._ensureLearningState().reanchored??null},i.learningCompletedRooms=function(){return[...this._ensureLearningState().completedRooms]},i.learningNextRoom=function(){return this._ensureLearningState().nextRoom??null},i.learningJobActive=function(){return this._dashboardJobIsActive()?!0:!!this._ensureLearningState().jobActive},i.learningSummary=function(){return this._ensureLearningState().summary??null},i.hasLearningSummary=function(){return!!this._ensureLearningState().summary},i.clearLearningSummary=function(){let e=this._ensureLearningState();e.summary=null},i.roomEstimates=function(){return this._ensureLearningState().roomEstimates??{}},i.roomEstimateMeta=function(){return this._ensureLearningState().roomEstimateMeta??{}},i.hasRoomEstimates=function(){return Object.keys(this.roomEstimates()).length>0},i.roomEstimateForRoom=function(e){let t=String(e),r=this.roomEstimates();for(let[a,n]of Object.entries(r))if(String(a)===t)return n??null;return null},i.roomEstimatesStatsStale=function(){return!!this.roomEstimateMeta().stats_stale},i.roomEstimatesStatsRebuiltAt=function(){return this.roomEstimateMeta().stats_rebuilt_at??null},i.roomEstimatesEstimatedAt=function(){return this.roomEstimateMeta().estimated_at??null},i.roomEstimateCount=function(){let e=Number(this.roomEstimateMeta().room_count);return Number.isFinite(e)?e:Object.keys(this.roomEstimates()).length},i.setLearningEstimate=function(e){let t=this._ensureLearningState();t.estimate=e??null},i.setDashboardSnapshot=function(e){let t=this._ensureLearningState();t.dashboardSnapshot=e??null},i.setLearningReanchored=function(e){let t=this._ensureLearningState();t.reanchored=e??null},i.setLearningNextRoom=function(e){let t=this._ensureLearningState();t.nextRoom=e??null},i.setLearningJobActive=function(e){let t=this._ensureLearningState();t.jobActive=!!e},i.setLearningCompletedRooms=function(e){let t=this._ensureLearningState();t.completedRooms=Array.isArray(e)?[...e]:[]},i.setRoomEstimates=function(e){let t=this._ensureLearningState(),r={};for(let a of e?.rooms??[])a?.room_id!=null&&(r[a.room_id]=a);t.roomEstimates=r,t.roomEstimateMeta={stats_stale:!!e?.stats_stale,stats_rebuilt_at:e?.stats_rebuilt_at??null,estimated_at:e?.estimated_at??null,room_count:Number(e?.room_count??Object.keys(r).length)||0,current_battery:e?.current_battery??null,map_id:e?.map_id??null,vacuum_entity_id:e?.vacuum_entity_id??null}},i.clearRoomEstimates=function(){let e=this._ensureLearningState();e.roomEstimates={},e.roomEstimateMeta={stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}},i.pushCompletedLearningRoom=function(e){let t=this._ensureLearningState();if(!e||e.room_id==null)return;let r=Number(e.actual_duration_minutes);Number.isFinite(r)&&t.completedRooms.push({room_id:e.room_id,actual_duration_minutes:r})},i.beginLearningJob=function(){let e=this._ensureLearningState();e.jobActive=!0,e.reanchored=e.estimate??null,e.completedRooms=[],e.nextRoom=null,e.summary=null},i.endLearningJob=function(e=null){let t=this._ensureLearningState(),r=t.estimate,a=t.reanchored??r,n=Array.isArray(t.completedRooms)?t.completedRooms:[],c=Number(e?.actual_cleaning_minutes??e?.duration_minutes),s=Number(e?.room_count),o=Number(a?.total_minutes??r?.total_minutes??0);r||a||n.length||e?t.summary={finished_at:new Date().toISOString(),total_minutes:Number.isFinite(c)&&c>0?c:o||0,rooms_completed:Number.isFinite(s)&&s>0?s:n.length,predicted_total_minutes:o||null,battery_warning:!!a?.battery_warning,final_payload:a??r??null}:t.summary=null,t.jobActive=!1,t.reanchored=null,t.completedRooms=[],t.nextRoom=null},i.hasLearningEstimate=function(){let e=this.learningEstimate();return!!e&&!e?.error},i.learningEstimateError=function(){return this.learningEstimate()?.error??null},i.learningEstimateErrorDetail=function(){return this.learningEstimate()?.error_detail??null},i.learningStatsStale=function(){return!!this.learningEstimate()?.stats_stale},i.learningBatteryWarning=function(){return!!(this.dashboardJobProgress()??this.learningReanchored()??this.learningEstimate())?.battery_warning},i.learningCanRenderEstimatePanel=function(){let e=this.learningEstimate();return!(!e||e.error)},i.learningTotalMinutes=function(){let e=Number(this.dashboardPlannedJobEstimateTotalMinutes()??this.learningEstimate()?.total_minutes);return Number.isFinite(e)?e:null},i.learningJobEtaAt=function(){return this.dashboardJobProgress()?.status_summary?.eta_at??this.dashboardPlannedJobEstimate()?.job_eta_at??this.learningEstimate()?.job_eta_at??null},i.learningConfidenceBreakpoint=function(){return this.dashboardPlannedJobEstimate()?.confidence_breakpoint??this.learningEstimate()?.confidence_breakpoint??null},i.learningRoomTimeline=function(){let e=this.dashboardJobProgressTimeline();if(e.length)return e;let t=this.dashboardPlannedJobEstimate()?.room_timeline;if(Array.isArray(t)&&t.length)return t;let r=this.learningReanchored()??this.learningEstimate();return Array.isArray(r?.room_timeline)?r.room_timeline:[]},i.learningRoomsCompletedCount=function(){let e=this.dashboardJobProgress()?.completed_room_ids;if(Array.isArray(e))return e.length;let t=this.learningReanchored(),r=Number(t?.rooms_completed);return Number.isFinite(r)?r:this._ensureLearningState().completedRooms.length},i.learningRoomsRemainingCount=function(){let e=this.dashboardJobProgress()?.remaining_room_ids;if(Array.isArray(e))return e.length;let t=this.learningReanchored(),r=Number(t?.rooms_remaining);return Number.isFinite(r)?r:this.learningRoomTimeline().filter(n=>!n?.completed).length},i.learningAllCompleted=function(){let e=this.dashboardJobProgress();if(e&&typeof e.terminal=="boolean")return e.terminal;let t=this.learningReanchored();if(typeof t?.all_completed=="boolean")return t.all_completed;let r=this.learningNextRoom();return!!(r&&Object.keys(r).length===0)},i.learningLiveBannerRoom=function(){let e=this.dashboardJobProgress()?.current_room_id;if(e!=null){let r=this.learningTimelineEntryForRoom(e);if(r)return r}let t=this.learningRoomTimeline().find(r=>!!r?.current);return t||this.learningNextRoom()},i.learningTimelineEntryForRoom=function(e){let t=String(e);return this.learningRoomTimeline().find(r=>String(r?.room_id)===t)??null}}function _r(i){i._ensureSetupState=function(){return this._setupState||(this._setupState={status:null,loading:!1,error:null,lastResult:null}),this._setupState},i.setupStatus=function(){return this._ensureSetupState().status??null},i.setSetupStatus=function(e){this._ensureSetupState().status=e??null},i.setupLoading=function(){return this._ensureSetupState().loading},i.setSetupLoading=function(e){this._ensureSetupState().loading=!!e},i.setupError=function(){return this._ensureSetupState().error??null},i.setSetupError=function(e){this._ensureSetupState().error=e??null},i.setupLastResult=function(){return this._ensureSetupState().lastResult??null},i.setSetupLastResult=function(e){this._ensureSetupState().lastResult=e??null},i._ensureSetupRoomEditor=function(){return this._setupRoomEditor||(this._setupRoomEditor={openMapId:null,rooms:null,loadingMapId:null,enabled:{},floorTypes:{},saving:!1,configuredMapIds:{}}),this._setupRoomEditor},i.setupRoomEditorOpenMapId=function(){return this._ensureSetupRoomEditor().openMapId??null},i.setupRoomEditorRooms=function(){return this._ensureSetupRoomEditor().rooms??null},i.setupRoomEditorLoadingMapId=function(){return this._ensureSetupRoomEditor().loadingMapId??null},i.setupRoomEditorSaving=function(){return this._ensureSetupRoomEditor().saving},i.isSetupMapConfigured=function(e){return!!this._ensureSetupRoomEditor().configuredMapIds[String(e)]},i.setSetupRoomEditorLoadingMapId=function(e){this._ensureSetupRoomEditor().loadingMapId=e??null},i.openSetupRoomEditor=function(e,t){let r=this._ensureSetupRoomEditor();r.openMapId=e,r.rooms=t,r.loadingMapId=null;let a={},n={};for(let c of t){let s=String(c.room_id);a[s]=!0,n[s]=c.floor_type||"hardwood"}r.enabled=a,r.floorTypes=n},i.closeSetupRoomEditor=function(){let e=this._ensureSetupRoomEditor();e.openMapId=null,e.rooms=null},i.toggleSetupRoom=function(e){let t=this._ensureSetupRoomEditor(),r=String(e);t.enabled[r]=t.enabled[r]===!1},i.setSetupRoomFloorType=function(e,t){this._ensureSetupRoomEditor().floorTypes[String(e)]=t},i.setSetupRoomEditorSaving=function(e){this._ensureSetupRoomEditor().saving=!!e},i.markSetupMapConfigured=function(e){this._ensureSetupRoomEditor().configuredMapIds[String(e)]=!0},i._ensureSetupDeleteState=function(){return this._setupDeleteState||(this._setupDeleteState={pendingMapId:null,stage:null,typedToken:"",deleting:!1}),this._setupDeleteState},i.setupDeletePendingMapId=function(){return this._ensureSetupDeleteState().pendingMapId??null},i.setupDeleteStage=function(){return this._ensureSetupDeleteState().stage??null},i.setupDeleteTypedToken=function(){return this._ensureSetupDeleteState().typedToken??""},i.setupDeleteDeleting=function(){return this._ensureSetupDeleteState().deleting},i.openSetupDeleteConfirm=function(e,t){let r=this._ensureSetupDeleteState();r.pendingMapId=e,r.stage=t?"typing":"confirm",r.typedToken="",r.deleting=!1},i.setSetupDeleteTypedToken=function(e){this._ensureSetupDeleteState().typedToken=e??""},i.setSetupDeleteDeleting=function(e){this._ensureSetupDeleteState().deleting=!!e},i.closeSetupDeleteConfirm=function(){let e=this._ensureSetupDeleteState();e.pendingMapId=null,e.stage=null,e.typedToken="",e.deleting=!1},i.setupRoomEditorEnabledIds=function(){let e=this._ensureSetupRoomEditor();return(e.rooms??[]).filter(r=>e.enabled[String(r.room_id)]!==!1).map(r=>r.room_id)},i.setupRoomEditorFloorTypesMap=function(){return{...this._ensureSetupRoomEditor().floorTypes}}}var xe={ALL:"all",HAS_BOUNDS:"has_bounds",NO_BOUNDS:"no_bounds"};function br(i){i._ensureMappingReviewState=function(){return this._mappingReviewState||(this._mappingReviewState={snapshot:null,filter:xe.ALL,pendingClearRoomId:null,pendingJobAction:null,pendingRebuildRoomId:null}),this._mappingReviewState},i.mappingBoundsSnapshot=function(){return this._ensureMappingReviewState().snapshot??null},i.setMappingBoundsSnapshot=function(e){this._ensureMappingReviewState().snapshot=e??null},i.mappingBoundsFilter=function(){return this._ensureMappingReviewState().filter},i.setMappingBoundsFilter=function(e){let t=this._ensureMappingReviewState();t.filter=Object.values(xe).includes(e)?e:xe.ALL},i.beginMappingBoundsClear=function(e){this._ensureMappingReviewState().pendingClearRoomId=String(e)},i.endMappingBoundsClear=function(){this._ensureMappingReviewState().pendingClearRoomId=null},i.isMappingBoundsClearPending=function(e){return this._ensureMappingReviewState().pendingClearRoomId===String(e)},i.beginMappingJobAction=function(e,t,r){this._ensureMappingReviewState().pendingJobAction={roomId:String(e),jobIndex:Number(t),action:r}},i.endMappingJobAction=function(){this._ensureMappingReviewState().pendingJobAction=null},i.isMappingJobActionPending=function(e,t){let r=this._ensureMappingReviewState().pendingJobAction;return r!==null&&r.roomId===String(e)&&r.jobIndex===Number(t)},i.beginMappingRebuild=function(e){this._ensureMappingReviewState().pendingRebuildRoomId=String(e)},i.endMappingRebuild=function(){this._ensureMappingReviewState().pendingRebuildRoomId=null},i.isMappingRebuildPending=function(e){return this._ensureMappingReviewState().pendingRebuildRoomId===String(e)},i.mappingBoundsFilterOptions=function(){return[{value:xe.ALL,label:"All Rooms"},{value:xe.HAS_BOUNDS,label:"Has Bounds"},{value:xe.NO_BOUNDS,label:"No Bounds"}]}}var D=class{constructor(e,t){this.hass=e,this.config=t}sync(e,t){return this.hass=e,this.config=t,this}};jt(D.prototype);zt(D.prototype);Vt(D.prototype);qt(D.prototype);Gt(D.prototype);Ut(D.prototype);Kt(D.prototype);Yt(D.prototype);Qt(D.prototype);Xt(D.prototype);Zt(D.prototype);er(D.prototype);rr(D.prototype);ar(D.prototype);hr(D.prototype);fr(D.prototype);gr(D.prototype);_r(D.prototype);br(D.prototype);function yr(i){i.escapeHtml=function(e){return String(e??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")},i.renderSelect=function(e,t,r,a,n=!1){let c=Array.isArray(r)?r:[];return`
      <label class="evcc-field">
        <span class="evcc-field-label">${this.escapeHtml(e)}</span>
        <select class="${this.escapeHtml(t)}" ${n?"disabled":""}>
          ${c.map(s=>{let o=typeof s=="object"?s.value:s,l=typeof s=="object"?s.label:s,d=String(o)===String(a)?"selected":"";return`<option value="${this.escapeHtml(String(o??""))}" ${d}>
                      ${this.escapeHtml(String(l??""))}
                    </option>`}).join("")}
        </select>
      </label>
    `},i.renderChipSelect=function(e,t,r,a,n=!1){let c=Array.isArray(r)?r:[];return`
      <div class="evcc-chip-select ${this.escapeHtml(t)}">
        ${e?`<div class="evcc-field-label">${this.escapeHtml(e)}</div>`:""}
        <div class="evcc-chips" role="listbox">
          ${c.map(s=>{let o=typeof s=="object"?s.value:s,l=typeof s=="object"?s.label:s;return`<button
                      type="button"
                      class="evcc-chip ${String(o)===String(a)?"active":""}"
                      data-value="${this.escapeHtml(String(o??""))}"
                      ${n?"disabled":""}
                    >${this.escapeHtml(String(l??""))}</button>`}).join("")}
        </div>
      </div>
    `},i.renderStatusBadge=function(e,t=""){return`
      <span class="evcc-status-badge ${this.escapeHtml(t)}">
        ${this.escapeHtml(e)}
      </span>
    `},i.formatTimestamp=function(e,t={},r=""){if(!e)return r;let a=new Date(e);return Number.isNaN(a.getTime())?r:a.toLocaleString([],t)}}function xr(i){i.renderBaseStationView=function(e){let{state:t}=e,r=t.dashboardUpkeep?.()??{},a=t.dockStatusLabel?.()??t.dockStatus?.()??r.dock_status_label??r.dock_status??null,n=t.dockLifecycleStateLabel?.()??t.dockLifecycleState?.()??null,c=t.dockTaskStatusLabel?.()??t.dockTaskStatus?.()??null,s=t.isDocked?.()??!1,o=t.dockActionStatus?.()??null,l=t.dashboardPlannedWaterEstimate?.()??null,d=r.dock_events??{},u=t.pauseTimeoutMinutesDefault?.(),v=[this._renderDockActionCard("wash_mop","Wash Mop",t),this._renderDockActionCard("dry_mop","Dry Mop",t),this._renderDockActionCard("stop_dry_mop","Stop Drying",t),this._renderDockActionCard("empty_dust","Empty Dust",t)].join("");return`
      <div class="evcc-base-station-view">
        <div class="evcc-base-station-grid">

          <section class="evcc-base-station-panel">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">Station Status</div>
                <div class="evcc-base-station-panel-subtitle">
                  ${this.escapeHtml(r.attention_summary||"Dock, lifecycle, and robot task state")}
                </div>
              </div>
            </div>

            <div class="evcc-base-station-stats">
              ${this._renderBaseStationStat("Dock Status",a||"Unknown")}
              ${this._renderBaseStationStat("Lifecycle",n||"Unknown")}
              ${this._renderBaseStationStat("Task",c||"Unknown")}
              ${this._renderBaseStationStat("Docked",s?"Yes":"No")}
            </div>

            ${r.updated_at||o?.updated_at?`
              <div class="evcc-base-station-updated">
                Updated ${this.escapeHtml(this._formatBaseStationTimestamp(o?.updated_at??r.updated_at))}
              </div>
            `:""}
          </section>

          <section class="evcc-base-station-panel">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">Water</div>
                <div class="evcc-base-station-panel-subtitle">
                  Current dock water plus projected post-job tank level
                </div>
              </div>
            </div>

            <div class="evcc-base-station-stats">
              ${this._renderBaseStationStat("Station Water",t.stationWaterLabel?.()||this._formatBaseStationWaterLevel(r.station_water))}
              ${this._renderBaseStationStat("Tank Now",this._formatBaseStationMilliliters(l?.available_clean_tank_ml))}
              ${this._renderBaseStationStat("After Job",this._formatBaseStationProjectedTank(l))}
              ${this._renderBaseStationStat("Job Use",this._formatBaseStationMilliliters(l?.estimated_total_dock_clean_water_used_ml))}
            </div>
          </section>

          <section class="evcc-base-station-panel evcc-base-station-panel--wide">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">Recent Dock Activity</div>
                <div class="evcc-base-station-panel-subtitle">
                  Last known mop wash, dust empty, and drying activity
                </div>
              </div>
            </div>

            <div class="evcc-base-station-activity-grid">
              ${this._renderBaseStationActivityCard("Mop Wash",d.last_mop_wash,d.mop_wash_count)}
              ${this._renderBaseStationActivityCard("Dust Empty",d.last_dust_empty,d.dust_empty_count)}
              ${this._renderBaseStationActivityCard("Dry Start",d.last_dry_start,d.dry_start_count,d.last_dry_duration)}
            </div>
          </section>

          <section class="evcc-base-station-panel evcc-base-station-panel--wide">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">Pause Timeout</div>
                <div class="evcc-base-station-panel-subtitle">
                  Default pause timeout used when a run is paused
                </div>
              </div>
            </div>

            <div class="evcc-chips">
              ${[15,30,45,60].map(m=>`
                <button
                  type="button"
                  class="evcc-chip ${u===m?"active":""}"
                  data-pause-timeout-minutes="${m}"
                >${m} min</button>
              `).join("")}
            </div>
          </section>

          <section class="evcc-base-station-panel evcc-base-station-panel--wide">
            <div class="evcc-base-station-panel-header">
              <div>
                <div class="evcc-base-station-panel-title">Dock Actions</div>
                <div class="evcc-base-station-panel-subtitle">
                  Backend-gated dock controls
                </div>
              </div>
            </div>

            <div class="evcc-base-station-action-grid">
              ${v}
            </div>
          </section>

        </div>
      </div>
    `},i._renderBaseStationStat=function(e,t){return`
      <div class="evcc-base-station-stat">
        <div class="evcc-base-station-stat-value">${this.escapeHtml(t)}</div>
        <div class="evcc-base-station-stat-label">${this.escapeHtml(e)}</div>
      </div>
    `},i._renderBaseStationActivityCard=function(e,t,r,a=null){return`
      <div class="evcc-base-station-activity-card">
        <div class="evcc-base-station-activity-title">${this.escapeHtml(e)}</div>
        <div class="evcc-base-station-activity-time">${this.escapeHtml(this._formatBaseStationTimestamp(t)||"No activity yet")}</div>
        <div class="evcc-base-station-activity-detail">
          ${this.escapeHtml(`${Number(r??0)} recorded`)}
          ${a!=null&&a!==""?` \xB7 ${this.escapeHtml(this._formatBaseStationDuration(a))}`:""}
        </div>
      </div>
    `},i._renderDockActionCard=function(e,t,r){let a=r.dockActionGate?.(e)??{},n=a?.allowed===!0,c=r.isDockActionPending?.(e)??!1,s=a?.reason_label??"",o=a?.message??"";return`
      <button
        type="button"
        class="evcc-base-station-action-card ${n?"evcc-base-station-action-card--allowed":"evcc-base-station-action-card--blocked"}"
        data-dock-action="${this.escapeHtml(e)}"
        ${n&&!c?"":"disabled"}
        title="${this.escapeHtml(o||s||(n?t:"Action unavailable"))}"
      >
        <div class="evcc-base-station-action-title">${this.escapeHtml(t)}</div>
        <div class="evcc-base-station-action-state">
          ${this.escapeHtml(c?"Running...":n?"Ready":"Unavailable")}
        </div>
        <div class="evcc-base-station-action-detail">
          ${this.escapeHtml(o||s||"Action available")}
        </div>
      </button>
    `},i._formatBaseStationLabel=function(e){let t=String(e??"").trim();return t?t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Unknown"},i._formatBaseStationTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatBaseStationMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"Unknown"},i._formatBaseStationProjectedTank=function(e){let t=Number(e?.estimated_clean_tank_remaining_ml),r=Number(e?.estimated_clean_tank_remaining_percent);return Number.isFinite(t)?Number.isFinite(r)?`${Math.round(t)} ml (${Math.round(r)}%)`:`${Math.round(t)} ml`:"Unknown"},i._formatBaseStationWaterLevel=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)}%`:this._formatBaseStationLabel(e)},i._formatBaseStationDuration=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:String(e??"")}}function wr(i){i.renderMetricsView=function(e){let{state:t}=e,r=t.metricsSnapshot?.();if(!r)return'<div class="evcc-empty">Loading metrics...</div>';if(r.available===!1)return`
        <div class="evcc-metrics-view">
          <div class="evcc-empty">
            ${this.escapeHtml(r.message||r.reason||"Metrics unavailable.")}
          </div>
        </div>
      `;let a=t.metricsOverview?.()??{},n=a.metrics??{},c=a.metric_windows??{},s=t.metricsActiveTab?.()??"learning";return`
      <div class="evcc-metrics-view">
        <div class="evcc-metrics-grid">
          <section class="evcc-metrics-panel">
            <div class="evcc-metrics-panel-header">
              <div>
                <div class="evcc-metrics-panel-title">Metrics</div>
                <div class="evcc-metrics-panel-subtitle">
                  ${this.escapeHtml(r.message||"Usage, learning quality, water, and dock metrics across the learning dataset.")}
                </div>
              </div>
            </div>

            <div class="evcc-metrics-stats">
              ${this._renderMetricsStat("Jobs",n.job_count??0)}
              ${this._renderMetricsStat("Used",n.learning_used_count??0)}
              ${this._renderMetricsStat("Excluded",n.excluded_count??0)}
              ${this._renderMetricsStat("Updated",this._formatMetricsTimestamp(r.updated_at)||"Unknown")}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-panel-header">
              <div>
                <div class="evcc-metrics-panel-title">Filters</div>
                <div class="evcc-metrics-panel-subtitle">Focus the metrics by room, profile, status, or learning use.</div>
              </div>
            </div>

            <div class="evcc-metrics-filters">
              ${this._renderMetricsChipFilter("Room","room_slug",t.metricsFilterRoomOptions?.(),t.metricsFilters?.().room_slug,"All Rooms")}
              ${this._renderMetricsChipFilter("Profile","profile_key",t.metricsFilterProfileOptions?.().map(o=>({value:o?.value,label:o?.label??o?.value??"Profile",title:o?.subtitle?`${o?.label??o?.value??"Profile"} | ${o.subtitle}`:o?.label??o?.value??"Profile"})),t.metricsFilters?.().profile_key,"All Profiles")}
              ${this._renderMetricsChipFilter("Status","status",t.metricsFilterStatusOptions?.(),t.metricsFilters?.().status,"All Statuses")}
              ${this._renderMetricsChipFilter("Learning Use","used_for_learning",t.metricsFilterUsedOptions?.().map(o=>({value:o?.value_key??o?.value,label:o?.label??o?.value_key??o?.value})),t.metricsFilters?.().used_for_learning,"All Learning Use")}
            </div>
          </section>

          <section class="evcc-metrics-panel evcc-metrics-panel--wide">
            <div class="evcc-metrics-tabs" role="tablist" aria-label="Metrics groups">
              ${t.metricsTabOptions?.().map(o=>`
                <button
                  type="button"
                  class="evcc-chip evcc-metrics-tab ${s===o.value?"active":""}"
                  data-metrics-tab="${this.escapeHtml(o.value)}"
                  role="tab"
                  aria-selected="${s===o.value?"true":"false"}"
                >${this.escapeHtml(o.label)}</button>
              `).join("")}
            </div>

            <div class="evcc-metrics-tab-panel">
              ${this._renderMetricsTabContent(s,t,n,c)}
            </div>
          </section>
        </div>
      </div>
    `},i._renderMetricsTabContent=function(e,t,r,a){switch(e){case"rooms":return this._renderMetricsRoomsTab(t);case"profiles":return this._renderMetricsProfilesTab(t);case"water":return this._renderMetricsWaterTab(t,r);case"dock":return this._renderMetricsDockTab(r,t);case"battery":return this._renderMetricsBatteryTab(t);default:return this._renderMetricsLearningTab(t,r,a)}},i._renderMetricsLearningTab=function(e,t,r){let a=e.metricsFoundProfiles?.()??[],n=e.metricsLearningStats?.()??{},c=Array.isArray(n.exact)?n.exact.length:0,s=Array.isArray(n.baselines)?n.baselines.length:0,o=Array.isArray(n.accuracy)?n.accuracy.length:0;return`
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-window-grid">
          ${this._renderMetricsWindowCard("Today",r.today)}
          ${this._renderMetricsWindowCard("Last 7 Days",r.last_7_days)}
          ${this._renderMetricsWindowCard("Last 30 Days",r.last_30_days)}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Found Profiles",a.length,"Profiles with learning history attached")}
          ${this._renderMetricsMiniCard("Exact Stats",c,"Exact room-learning stat groups")}
          ${this._renderMetricsMiniCard("Baselines",s,"Room baseline groups")}
          ${this._renderMetricsMiniCard("Accuracy Rows",o,"Accuracy stat rows")}
          ${this._renderMetricsMiniCard("Recharge Count",t.mid_job_recharge_count??0,"Observed mid-job recharges")}
          ${this._renderMetricsMiniCard("Wash Cycles",t.wash_cycle_count??0,"Wash cycles recorded from jobs")}
        </div>

        ${a.length?`
          <div class="evcc-metrics-card-grid">
            ${a.slice(0,8).map(l=>this._renderMetricsFoundProfileCard(l)).join("")}
          </div>
        `:`
          <div class="evcc-metrics-empty">No found profiles were returned for the current filters.</div>
        `}
      </div>
    `},i._renderMetricsRoomsTab=function(e){let t=e.metricsRooms?.()??[];return t.length?`
      <div class="evcc-metrics-card-grid">
        ${t.map(r=>this._renderMetricsRoomCard(r)).join("")}
      </div>
    `:'<div class="evcc-metrics-empty">No room metrics matched the current filters.</div>'},i._renderMetricsProfilesTab=function(e){let t=e.metricsRoomProfiles?.()??[],r=e.metricsFoundProfiles?.()??[];return`
      <div class="evcc-metrics-section-stack">
        ${t.length?`
          <div class="evcc-metrics-card-grid">
            ${t.map(a=>this._renderMetricsRoomProfileCard(a)).join("")}
          </div>
        `:`
          <div class="evcc-metrics-empty">No room-profile metrics matched the current filters.</div>
        `}

        ${r.length?`
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Found Profiles</div>
              <div class="evcc-metrics-panel-subtitle">Detected profile families and trust state.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${r.slice(0,12).map(a=>this._renderMetricsFoundProfileCard(a)).join("")}
          </div>
        `:""}
      </div>
    `},i._renderMetricsWaterTab=function(e,t){let r=[...e.metricsRooms?.()??[]].sort((n,c)=>Number(c?.avg_total_water_used_ml??0)-Number(n?.avg_total_water_used_ml??0)).slice(0,8),a=[...e.metricsRoomProfiles?.()??[]].sort((n,c)=>Number(c?.avg_total_water_used_ml??0)-Number(n?.avg_total_water_used_ml??0)).slice(0,8);return`
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Robot Water",this._formatMetricsMilliliters(t.total_robot_water_used_ml),"Robot-applied cleaning water")}
          ${this._renderMetricsMiniCard("Water Overhead",this._formatMetricsMilliliters(t.total_water_overhead_ml),"Dock or wash overhead water")}
          ${this._renderMetricsMiniCard("Total Water",this._formatMetricsMilliliters(t.total_water_used_ml),"Total water used across matching jobs")}
        </div>

        ${r.length?`
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Highest Water Rooms</div>
              <div class="evcc-metrics-panel-subtitle">Average total water use per room.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${r.map(n=>this._renderMetricsWaterRoomCard(n)).join("")}
          </div>
        `:""}

        ${a.length?`
          <div class="evcc-metrics-panel-header">
            <div>
              <div class="evcc-metrics-panel-title">Highest Water Profiles</div>
              <div class="evcc-metrics-panel-subtitle">Average total water use per profile.</div>
            </div>
          </div>
          <div class="evcc-metrics-card-grid">
            ${a.map(n=>this._renderMetricsWaterProfileCard(n)).join("")}
          </div>
        `:""}
      </div>
    `},i._renderMetricsDockTab=function(e,t){let r=e?.dock??{},a=t.metricsSources?.()??{};return`
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Mop Wash",r.mop_wash_count??0,"Dock mop wash count")}
          ${this._renderMetricsMiniCard("Dust Empty",r.dust_empty_count??0,"Dock dust-empty count")}
          ${this._renderMetricsMiniCard("Dry Starts",r.dry_start_count??0,"Dock dry-start count")}
          ${this._renderMetricsMiniCard("Wash Cycles",r.wash_cycle_count_from_jobs??0,"Wash cycles inferred from jobs")}
          ${this._renderMetricsMiniCard("Water Overhead",this._formatMetricsMilliliters(r.total_water_overhead_ml),"Total dock water overhead")}
          ${this._renderMetricsMiniCard("Avg Overhead / Job",this._formatMetricsMilliliters(r.avg_water_overhead_ml_per_job),"Average water overhead per job")}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Last Mop Wash",this._formatMetricsTimestamp(r.last_mop_wash)||"Unknown","Latest dock mop wash")}
          ${this._renderMetricsMiniCard("Last Dust Empty",this._formatMetricsTimestamp(r.last_dust_empty)||"Unknown","Latest dock dust empty")}
          ${this._renderMetricsMiniCard("Last Dry Start",this._formatMetricsTimestamp(r.last_dry_start)||"Unknown","Latest dock dry start")}
          ${this._renderMetricsMiniCard("Last Dry Duration",this._formatMetricsDurationValue(r.last_dry_duration),"Latest dock dry duration")}
          ${this._renderMetricsMiniCard("Room Stats Rebuilt",this._formatMetricsTimestamp(a.room_stats_rebuilt_at)||"Unknown","Latest room stat rebuild")}
          ${this._renderMetricsMiniCard("Accuracy Updated",this._formatMetricsTimestamp(a.accuracy_stats_updated_at)||"Unknown","Latest accuracy update")}
        </div>
      </div>
    `},i._renderMetricsSelect=function(e,t,r,a,n){let c=Array.isArray(r)?r:[],s=[{value:"",label:n},...c.filter(o=>String(o?.value??"")!=="")];return`
      <label class="evcc-field evcc-metrics-filter">
        <span class="evcc-field-label">${this.escapeHtml(e)}</span>
        <select data-metrics-filter="${this.escapeHtml(t)}">
          ${s.map(o=>`
            <option
              value="${this.escapeHtml(String(o?.value??""))}"
              ${String(o?.value??"")===String(a??"")?"selected":""}
            >${this.escapeHtml(String(o?.label??o?.value??""))}</option>
          `).join("")}
        </select>
      </label>
    `},i._renderMetricsChipFilter=function(e,t,r,a,n){let s=(Array.isArray(r)?r:[]).filter(l=>l&&typeof l=="object").map(l=>({value:String(l?.value??""),label:String(l?.label??l?.value??""),title:String(l?.title??l?.label??l?.value??"")})),o=[{value:"",label:n},...s.filter(l=>l.value!=="")];return`
      <div class="evcc-metrics-chip-filter">
        <div class="evcc-field-label">${this.escapeHtml(e)}</div>
        <div class="evcc-chips evcc-metrics-filter-chips">
          ${o.map(l=>`
            <button
              type="button"
              class="evcc-chip ${String(l.value)===String(a??"")?"active":""}"
              data-metrics-filter-chip="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(l.value)}"
              title="${this.escapeHtml(l.title)}"
            >${this.escapeHtml(l.label)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderMetricsStat=function(e,t){return`
      <div class="evcc-metrics-stat">
        <div class="evcc-metrics-stat-value">${this.escapeHtml(t)}</div>
        <div class="evcc-metrics-stat-label">${this.escapeHtml(e)}</div>
      </div>
    `},i._renderMetricsWindowCard=function(e,t){let r=t??{};return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(e)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(r.total_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(r.job_count??0)} jobs | ${Number(r.learning_used_count??0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Water ${this._formatMetricsMilliliters(r.total_water_used_ml)} | Recharge ${Number(r.mid_job_recharge_count??0)}`)}</div>
      </div>
    `},i._renderMetricsMiniCard=function(e,t,r=""){return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(e)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(t)}</div>
        ${r?`<div class="evcc-metrics-card-detail">${this.escapeHtml(r)}</div>`:""}
      </div>
    `},i._renderMetricsRoomCard=function(e){let t=e?.room_label||e?.room_slug||"Room";return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(t)}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(e?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(e?.run_count??0)} runs | ${Number(e?.learning_run_count??0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Trust ${this._formatMetricsTrustLevel(e?.trust_level)} | ${Number(e?.runs_to_trusted??0)} runs to trusted`)}</div>
      </div>
    `},i._renderMetricsRoomProfileCard=function(e){let t=e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Profile",r=e?.profile_subtitle||e?.room_label||e?.room_slug||"",a=this.card?._state?.metricsProfileSaveKey?.("profile",e)??"",n=this.card?._state?.isMetricsProfileSavePending?.(a)??!1,c=e?.save_candidate===!0&&e?.save_supported===!0&&String(e?.save_service??"").trim()!=="";return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(t)}</div>
          ${e?.save_candidate===!0?`
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.escapeHtml(e?.save_suggested_label||"Suggested save candidate")}">
              ${this.escapeHtml(e?.save_suggested_label||"Save Candidate")}
            </span>
          `:""}
        </div>
        ${r?`<div class="evcc-metrics-card-subtitle">${this.escapeHtml(r)}</div>`:""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsDuration(e?.avg_duration_minutes))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(e?.run_count??0)} runs | ${Number(e?.learning_run_count??0)} used`)}</div>
        <div class="evcc-metrics-card-secondary">${this.escapeHtml(`Water ${this._formatMetricsMilliliters(e?.avg_total_water_used_ml)} | Trust ${this._formatMetricsTrustLevel(e?.trust_level)}`)}</div>
        ${c?`
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="profile"
              data-profile-key="${this.escapeHtml(String(e?.profile_key??""))}"
              data-room-slug="${this.escapeHtml(String(e?.room_slug??""))}"
              ${n?"disabled":""}
              title="${this.escapeHtml(e?.save_suggested_label||"Save this learned profile")}"
            >${n?"Saving...":"Save Profile"}</button>
          </div>
        `:""}
      </div>
    `},i._renderMetricsFoundProfileCard=function(e){let t=e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Profile",r=e?.profile_subtitle||e?.room_label||e?.room_slug||"",a=e?.trust_reason_text||e?.trust_reason||"",n=this.card?._state?.metricsProfileSaveKey?.("found",e)??"",c=this.card?._state?.isMetricsProfileSavePending?.(n)??!1,s=e?.save_candidate===!0&&String(e?.save_service??"").trim()!=="";return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-header">
          <div class="evcc-metrics-card-title">${this.escapeHtml(t)}</div>
          ${e?.save_candidate===!0?`
            <span class="evcc-chip evcc-metrics-card-badge" title="${this.escapeHtml(e?.save_suggested_label||"Suggested save candidate")}">
              ${this.escapeHtml(e?.save_suggested_label||"Save Candidate")}
            </span>
          `:""}
        </div>
        ${r?`<div class="evcc-metrics-card-subtitle">${this.escapeHtml(r)}</div>`:""}
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsTrustLevel(e?.trust_level))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`${Number(e?.run_count??0)} runs | ${Number(e?.learning_run_count??0)} used`)}</div>
        ${a?`<div class="evcc-metrics-card-secondary">${this.escapeHtml(a)}</div>`:""}
        ${s?`
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="found"
              data-profile-key="${this.escapeHtml(String(e?.profile_key??""))}"
              data-room-slug="${this.escapeHtml(String(e?.room_slug??""))}"
              ${c?"disabled":""}
              title="${this.escapeHtml(e?.save_suggested_label||"Save this learned profile")}"
            >${c?"Saving...":"Save Profile"}</button>
          </div>
        `:""}
      </div>
    `},i._renderMetricsWaterRoomCard=function(e){return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(e?.room_label||e?.room_slug||"Room")}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(e?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`Robot ${this._formatMetricsMilliliters(e?.avg_robot_water_used_ml)} | Overhead ${this._formatMetricsMilliliters(e?.avg_water_overhead_ml)}`)}</div>
      </div>
    `},i._renderMetricsWaterProfileCard=function(e){return`
      <div class="evcc-metrics-card">
        <div class="evcc-metrics-card-title">${this.escapeHtml(e?.profile_label||e?.profile_key||"Profile")}</div>
        <div class="evcc-metrics-card-value">${this.escapeHtml(this._formatMetricsMilliliters(e?.avg_total_water_used_ml))}</div>
        <div class="evcc-metrics-card-detail">${this.escapeHtml(`Robot ${this._formatMetricsMilliliters(e?.avg_robot_water_used_ml)} | Overhead ${this._formatMetricsMilliliters(e?.avg_water_overhead_ml)}`)}</div>
      </div>
    `},i._formatMetricsDuration=function(e){let t=Number(e);return Number.isFinite(t)?this._formatLearningDuration(t):"0 min"},i._formatMetricsMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"0 ml"},i._formatMetricsTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatMetricsTrustLevel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())||"Unknown"},i._formatMetricsDurationValue=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:String(e??"Unknown")},i._renderMetricsBatteryTab=function(e){let t=e.batteryMetrics?.()??{},r=(g,R=2)=>{let S=Number(g);return Number.isFinite(S)?S.toFixed(R).replace(/\.?0+$/,""):"\u2014"},a=g=>{if(g==null)return!0;let R=String(g).trim().toLowerCase();return R===""||R==="unknown"||R==="unavailable"||R==="none"},n=(g,R=2,S="")=>{if(!g||a(g.state))return"\u2014";let P=Number(g.state);return Number.isFinite(P)?`${r(P,R)}${S}`:String(g.state)},c=`
      <div class="evcc-metrics-card-grid">
        ${this._renderMetricsMiniCard("Charge cycles",n(t.cycles,1),"Cumulative drain \xF7 100")}
        ${this._renderMetricsMiniCard("Health %",n(t.health,0,"%"),t.health?.attrs?.baseline_session_count?`vs first ${t.health.attrs.baseline_session_count} full charges`:"Building baseline")}
        ${this._renderMetricsMiniCard("Charge rate",n(t.rate_overall,2," %/min"),t.rate_overall?.attrs?.charging?"Charging now":"Last sample")}
        ${this._renderMetricsMiniCard("Last job %/m\xB2",n(t.last_job_per_m2,3),t.last_job_per_m2?.attrs?.area_m2?`${r(t.last_job_per_m2.attrs.area_m2,1)} m\xB2 | ${r(t.last_job_per_m2.attrs.battery_used_pct,0)} % used`:"Awaiting first job")}
      </div>
    `,s=`
      <div class="evcc-metrics-section-title">Charge rates by zone</div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>Zone</th>
            <th>Last rate</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Overall</td>
            <td>${this.escapeHtml(n(t.rate_overall,2," %/min"))}</td>
            <td>Any active charge interval</td>
          </tr>
          <tr>
            <td>Low (\u2264 29 %)</td>
            <td>${this.escapeHtml(n(t.rate_low,2," %/min"))}</td>
            <td>Slow precharge / soft-cell signal</td>
          </tr>
          <tr>
            <td>High (\u2265 80 %)</td>
            <td>${this.escapeHtml(n(t.rate_high,2," %/min"))}</td>
            <td>CV taper \u2014 earliest health drop indicator</td>
          </tr>
          <tr>
            <td>Mid-job (15\u219275)</td>
            <td>${this.escapeHtml(n(t.rate_mid_job,2," %/min"))}</td>
            <td>${this.escapeHtml(`Rolling mean | ${t.rate_mid_job?.attrs?.sample_count??0} samples`)}</td>
          </tr>
          <tr>
            <td>Last full session</td>
            <td>${this.escapeHtml(n(t.last_charge_duration,0," min"))}</td>
            <td>${this.escapeHtml(t.last_charge_duration?.attrs?.last_charge_delta_pct!=null?`Charged ${t.last_charge_duration.attrs.last_charge_delta_pct} %`:"")}</td>
          </tr>
        </tbody>
      </table>
    `,o=t.last_job_per_m2?.attrs?.by_clean_mode_mean??{},l=t.last_job_per_m2?.attrs?.by_fan_speed_mean??{},d=t.last_job_per_m2?.attrs?.by_water_level_mean??{},u=(g,R)=>{let S=Object.keys(g||{});return S.length?S.map(P=>`
        <tr>
          <td>${this.escapeHtml(P)}</td>
          <td>${this.escapeHtml(r(g[P]?.mean,3))}</td>
          <td>${this.escapeHtml(String(g[P]?.count??0))}</td>
        </tr>
      `).join(""):`<tr><td colspan="3"><em>${this.escapeHtml(R)} \u2014 no single-bucket jobs yet</em></td></tr>`},v=t.last_job_per_m2?.attrs?.all_jobs_count??0,m=t.last_job_per_m2?.attrs?.all_jobs_mean,p=`
      <div class="evcc-metrics-section-title">Drain per m\xB2 by single-bucket job</div>
      <div class="evcc-metrics-section-subtitle">
        Only jobs where every room used the same setting feed these means.
        Mixed-mode runs still update the all-jobs row but skip per-bucket buckets.
      </div>
      <table class="evcc-metrics-table">
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Mean %/m\xB2</th>
            <th>Jobs</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>All jobs (mixed + single)</strong></td>
            <td>${this.escapeHtml(r(m,3))}</td>
            <td>${this.escapeHtml(String(v))}</td>
          </tr>
          <tr><td colspan="3"><em>By clean mode</em></td></tr>
          ${u(o,"Clean mode")}
          <tr><td colspan="3"><em>By fan speed</em></td></tr>
          ${u(l,"Fan speed")}
          <tr><td colspan="3"><em>By water level</em></td></tr>
          ${u(d,"Water level")}
        </tbody>
      </table>
    `,f=t.last_job_per_m2?.attrs??{},h=f.post_job_charge??null,y=f.recorded_at?`
      <div class="evcc-metrics-section-title">Most recent completed job</div>
      <table class="evcc-metrics-table">
        <tbody>
          <tr><td>Job ID</td><td>${this.escapeHtml(String(f.job_id??"\u2014"))}</td></tr>
          <tr><td>Recorded</td><td>${this.escapeHtml(this._formatMetricsTimestamp(f.recorded_at)||"\u2014")}</td></tr>
          <tr><td>Duration</td><td>${this.escapeHtml(r(f.duration_min,1)+" min")}</td></tr>
          <tr><td>Area</td><td>${this.escapeHtml(r(f.area_m2,1)+" m\xB2")}</td></tr>
          <tr><td>Battery used</td><td>${this.escapeHtml(r(f.battery_used_pct,0)+" %")}</td></tr>
          <tr><td>Drain rate</td><td>${this.escapeHtml(n(t.last_job_per_min,2," %/min"))}</td></tr>
          <tr><td>Drain per hour</td><td>${this.escapeHtml(n(t.last_job_per_hour,1," %/h"))}</td></tr>
          <tr><td>Drain per m\xB2</td><td>${this.escapeHtml(n(t.last_job_per_m2,3," %/m\xB2"))}</td></tr>
          <tr><td>Single clean mode</td><td>${this.escapeHtml(f.single_clean_mode??"(mixed)")}</td></tr>
          <tr><td>Single fan speed</td><td>${this.escapeHtml(f.single_fan_speed??"(mixed)")}</td></tr>
          <tr><td>Single water level</td><td>${this.escapeHtml(f.single_water_level??"(mixed)")}</td></tr>
          <tr><td>Weighted by</td><td>${this.escapeHtml(f.weighted_by??"\u2014")}</td></tr>
          ${h?`
            <tr><td colspan="2"><em>Post-job recharge</em></td></tr>
            <tr><td>Recharge duration</td><td>${this.escapeHtml(r(h.duration_min,1)+" min")}</td></tr>
            <tr><td>Recharge delta</td><td>${this.escapeHtml(`${h.start_battery??"?"} \u2192 ${h.end_battery??"?"} %`)}</td></tr>
            <tr><td>Avg rate</td><td>${this.escapeHtml(r(h.avg_rate_per_min,2)+" %/min")}</td></tr>
            <tr><td>Ended</td><td>${this.escapeHtml(h.ended_reason??"\u2014")}</td></tr>
          `:`
            <tr><td>Post-job recharge</td><td><em>Awaiting next charge session</em></td></tr>
          `}
        </tbody>
      </table>
    `:`
      <div class="evcc-metrics-section-title">Most recent completed job</div>
      <div class="evcc-empty">No completed job yet \u2014 sensors populate after the first finalized run.</div>
    `,x=e.vacuumObjectId?.()??"",w=`
      <div class="evcc-metrics-section-title">Raw data files</div>
      <div class="evcc-metrics-section-subtitle">
        Long-term review is best done from the raw files written by the integration.
        Chart any of the sensors above with HA's history-graph or apexcharts-card; for
        deeper analysis open the CSV in a spreadsheet.
      </div>
      <pre class="evcc-metrics-codeblock">config/eufy_vacuum/battery/${this.escapeHtml(x)}/sessions.csv
config/eufy_vacuum/battery/${this.escapeHtml(x)}/samples.jsonl</pre>
    `;return`
      <div class="evcc-metrics-section-stack">
        ${c}
        ${s}
        ${p}
        ${y}
        ${w}
      </div>
    `}}function Sr(i){i.renderLearningReviewView=function(e){let{state:t}=e,r=t.learningHistorySnapshot?.();if(!r)return'<div class="evcc-empty">Loading learning history...</div>';if(r.available===!1)return`
        <div class="evcc-review-view">
          <div class="evcc-empty">
            ${this.escapeHtml(r.message||r.reason||"Learning history unavailable.")}
          </div>
        </div>
      `;let a=r.summary??{},n=this._getSortedLearningReviewJobs(t,r.jobs??[]);return`
      <div class="evcc-review-view">
        <div class="evcc-review-grid">

          <section class="evcc-review-panel">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Learning Review</div>
                <div class="evcc-review-panel-subtitle">
                  ${this.escapeHtml(r.message||"Review runs used for learning and exclude bad history when needed.")}
                </div>
              </div>
            </div>

            <div class="evcc-review-stats">
              ${this._renderReviewStat("Jobs",a?.filtered_job_count??a?.job_count??0)}
              ${this._renderReviewStat("Rooms",a?.filtered_room_count??0)}
              ${this._renderReviewStat("Profiles",a?.filtered_room_profile_count??0)}
              ${this._renderReviewStat("Updated",this._formatReviewTimestamp(r.updated_at)||"Unknown")}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Filters</div>
                <div class="evcc-review-panel-subtitle">Narrow to room, profile, status, or learning use.</div>
              </div>
            </div>

            <div class="evcc-review-filters">
              ${this._renderReviewChipFilter("Room","room_slug",t.learningHistoryRooms?.().map(c=>({value:c?.room_slug??c?.slug??"",label:c?.room_name??c?.label??c?.slug??"Room"})),t.learningHistoryFilters?.().room_slug,"All Rooms")}

              ${this._renderReviewChipFilter("Profile","profile_key",t.learningHistoryProfiles?.().map(c=>({value:c?.profile_key??"",label:c?.label??c?.profile_key??"Profile",title:c?.subtitle?`${c?.label??c?.profile_key??"Profile"} | ${c.subtitle}`:c?.label??c?.profile_key??"Profile"})),t.learningHistoryFilters?.().profile_key,"All Profiles")}

              ${this._renderReviewChipFilter("Status","status",t.learningHistoryStatusOptions?.(),t.learningHistoryFilters?.().status,"All Statuses")}

              ${this._renderReviewChipFilter("Learning Use","used_for_learning",t.learningHistoryUsedOptions?.(),t.learningHistoryFilters?.().used_for_learning,"All Learning Use")}

              ${this._renderReviewChipFilter("Sort","sort",t.learningHistorySortOptions?.(),t.learningHistorySort?.(),"Newest","",!0)}
            </div>
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Profile Matcher</div>
                <div class="evcc-review-panel-subtitle">Try room-editor settings locally to find exact learned profile matches without editing a live room.</div>
              </div>
            </div>

            ${this._renderReviewProfileMatcher(t)}
          </section>

          <section class="evcc-review-panel evcc-review-panel--wide">
            <div class="evcc-review-panel-header">
              <div>
                <div class="evcc-review-panel-title">Runs</div>
                <div class="evcc-review-panel-subtitle">Newest first unless another sort is selected.</div>
              </div>
            </div>

            ${n.length?`
              <div class="evcc-review-job-list">
                ${n.map(c=>this._renderLearningReviewJobCard(c,t)).join("")}
              </div>
            `:`
              <div class="evcc-review-empty">No learning history jobs matched the current filters.</div>
            `}
          </section>

        </div>
      </div>
    `},i._renderReviewStat=function(e,t){return`
      <div class="evcc-review-stat">
        <div class="evcc-review-stat-value">${this.escapeHtml(t)}</div>
        <div class="evcc-review-stat-label">${this.escapeHtml(e)}</div>
      </div>
    `},i._renderReviewSelect=function(e,t,r,a,n,c=!1){let s=Array.isArray(r)?r:[],o=s.length?s:[{value:"",label:n}],l=c?o:[{value:"",label:n},...o.filter(d=>String(d?.value??"")!=="")];return`
      <label class="evcc-field evcc-review-filter">
        <span class="evcc-field-label">${this.escapeHtml(e)}</span>
        <select data-review-filter="${this.escapeHtml(t)}">
          ${l.map(d=>`
            <option
              value="${this.escapeHtml(String(d?.value??""))}"
              ${String(d?.value??"")===String(a??"")?"selected":""}
            >${this.escapeHtml(String(d?.label??d?.value??""))}</option>
          `).join("")}
        </select>
      </label>
    `},i._renderReviewChipFilter=function(e,t,r,a,n,c="",s=!0){let l=(Array.isArray(r)?r:[]).filter(u=>u&&typeof u=="object").map(u=>({value:String(u?.value??""),label:String(u?.label??u?.value??""),title:String(u?.title??u?.label??u?.value??"")})),d=s?[{value:String(c),label:n},...l.filter(u=>u.value!==String(c))]:l;return`
      <div class="evcc-review-chip-filter">
        <div class="evcc-field-label">${this.escapeHtml(e)}</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${d.map(u=>`
            <button
              type="button"
              class="evcc-chip ${String(u.value)===String(a??"")?"active":""}"
              data-review-filter-chip="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(u.value)}"
              title="${this.escapeHtml(u.title)}"
            >${this.escapeHtml(u.label)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderReviewProfileMatcher=function(e){let t=e.reviewProfileMatcherFields?.();if(!t)return"";let r=e.reviewProfileMatcherMatches?.()??[],a=e.learningHistoryFilters?.().profile_key??"";return`
      <div class="evcc-review-matcher">
        <div class="evcc-review-matcher-grid">
          ${this._renderReviewMatcherField("Cleaning Mode","clean_mode",t.clean_mode,e.cleanModeOptions?.()??[])}
          ${this._renderReviewMatcherField("Suction Level","fan_speed",t.fan_speed,e.suctionLevelOptions?.()??[])}
          ${e.showReviewProfileMatcherWaterLevel?.()?this._renderReviewMatcherField("Water Level","water_level",t.water_level,e.waterLevelOptions?.()??[]):""}
          ${this._renderReviewMatcherField("Cleaning Path","clean_intensity",t.clean_intensity,e.cleanIntensityOptions?.()??[])}
          ${this._renderReviewMatcherField("Cleaning Passes","clean_passes",t.clean_passes,[{value:1,label:"1 Pass"},{value:2,label:"2 Passes"}])}
          ${e.showReviewProfileMatcherEdgeMopping?.()?this._renderReviewMatcherField("Edge Mopping","edge_mopping",t.edge_mopping,[{value:!0,label:"On"},{value:!1,label:"Off"}]):""}
        </div>

        <div class="evcc-review-matcher-actions">
          <button
            type="button"
            class="evcc-chip"
            data-review-matcher-action="reset"
          >Reset Matcher</button>
        </div>

        <div class="evcc-review-matcher-results">
          <div class="evcc-review-matcher-results-header">
            <div class="evcc-review-panel-title">Matched Profiles</div>
            <div class="evcc-review-panel-subtitle">
              ${r.length?this.escapeHtml(`${r.length} exact match${r.length===1?"":"es"} found.`):"No exact profile matches for the current settings."}
            </div>
          </div>

          ${r.length?`
            <div class="evcc-chips evcc-review-matcher-match-chips">
              ${r.map(n=>`
                <button
                  type="button"
                  class="evcc-chip ${String(a)===String(n.profile_key)?"active":""}"
                  data-review-matcher-profile="${this.escapeHtml(n.profile_key)}"
                  title="Filter learning jobs to this profile"
                >${this.escapeHtml(n.label??n.profile_key)}</button>
              `).join("")}
            </div>
          `:`
            <div class="evcc-review-empty">Adjust the matcher fields until they line up with a saved profile exactly.</div>
          `}
        </div>
      </div>
    `},i._renderReviewMatcherField=function(e,t,r,a){let n=(Array.isArray(a)?a:[]).map(c=>c&&typeof c=="object"&&"value"in c?{value:c.value,label:c.label??c.value}:{value:c,label:c}).filter(c=>c.value!=null&&String(c.value).trim()!=="");return n.length?`
      <div class="evcc-editor-field-group evcc-review-matcher-field">
        <div class="evcc-field-label">${this.escapeHtml(e)}</div>
        <div class="evcc-chips">
          ${n.map(c=>`
            <button
              type="button"
              class="evcc-chip ${String(c.value)===String(r)?"active":""}"
              data-review-matcher-field="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(String(c.value))}"
            >${this.escapeHtml(String(c.label))}</button>
          `).join("")}
        </div>
      </div>
    `:""},i._renderReviewReasonChips=function(e,t,r){let a=t.learningHistoryExcludeReason?.(e);return`
      <div class="evcc-review-reason-chips">
        <div class="evcc-field-label">Exclude Reason</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${(t.learningHistoryExcludeReasonOptions?.()??[]).map(c=>`
            <button
              type="button"
              class="evcc-chip ${String(c?.value??"")===String(a??"")?"active":""}"
              data-review-reason-chip="${this.escapeHtml(e)}"
              data-value="${this.escapeHtml(String(c?.value??""))}"
              ${r?"disabled":""}
            >${this.escapeHtml(String(c?.label??c?.value??""))}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderLearningReviewJobCard=function(e,t){let r=String(e?.job_id??""),a=t.isLearningHistoryJobActionPending?.(r)??!1,n=e?.exclude_allowed===!0,c=e?.restore_allowed===!0,s=e?.excluded_from_learning===!0,o=[];s&&o.push({text:"Excluded",cls:"evcc-review-badge--excluded"}),e?.exclude_suggested===!0&&o.push({text:e?.exclude_suggested_reason_label||"Suggested Exclude",cls:"evcc-review-badge--suggested"}),String(e?.status??"").trim().toLowerCase()!=="completed"&&o.push({text:e?.status_label||this._formatReviewLabel(e?.status||"Unknown"),cls:"evcc-review-badge--warning"}),e?.sanity_passed===!1&&o.push({text:"Sanity Failed",cls:"evcc-review-badge--warning"}),e?.mid_job_recharge_observed===!0&&o.push({text:"Recharge",cls:"evcc-review-badge--neutral"}),e?.is_single_room===!0&&o.push({text:"Single Room",cls:"evcc-review-badge--neutral"}),e?.is_multi_room===!0&&o.push({text:"Multi Room",cls:"evcc-review-badge--neutral"});let l=[this._formatReviewTimestamp(e?.started_at),Number.isFinite(Number(e?.duration_minutes))?`${Number(e.duration_minutes).toFixed(1).replace(/\.0$/,"")} min`:"",Number.isFinite(Number(e?.outlier_score))?`Outlier ${Number(e.outlier_score).toFixed(2)}`:"",Number.isFinite(Number(e?.battery_used))?`Battery ${Number(e.battery_used)}`:"",Number.isFinite(Number(e?.total_water_used_ml))&&Number(e.total_water_used_ml)>0?`Water ${Math.round(Number(e.total_water_used_ml))} ml`:""].filter(Boolean),d=e?.exclude_suggested_reason_text||e?.exclude_reason_text||e?.restore_reason_text||e?.status_text||(Array.isArray(e?.learning_blocker_texts)&&e.learning_blocker_texts.length?e.learning_blocker_texts.join(", "):"")||(Array.isArray(e?.sanity_flag_texts)&&e.sanity_flag_texts.length?e.sanity_flag_texts.join(", "):"")||e?.cancel_detection?.reason_text||e?.exclude_suggested_reason_label||e?.exclude_reason_label||e?.restore_reason_label||(Array.isArray(e?.learning_blockers)&&e.learning_blockers.length?e.learning_blockers.join(", "):"")||(Array.isArray(e?.sanity_flags)&&e.sanity_flags.length?e.sanity_flags.join(", "):""),u=e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Unknown",v=e?.profile_subtitle||null,m=Array.isArray(e?.room_slugs)&&e.room_slugs.length?e.room_slugs.join(", "):"Unknown",p=e?.primary_room_label||e?.primary_room_slug||"Unknown",f=e?.job_scope_label||(e?.job_scope?this._formatReviewLabel(e.job_scope):"Unknown");return`
      <article class="evcc-review-job-card ${s?"evcc-review-job-card--excluded":""} ${e?.exclude_suggested?"evcc-review-job-card--suggested":""}">
        <div class="evcc-review-job-header">
          <div>
            <div class="evcc-review-job-title">${this.escapeHtml(r)}</div>
            <div class="evcc-review-job-subtitle">${this.escapeHtml(l.join(" | "))}</div>
          </div>
          <div class="evcc-review-job-badges">
            ${o.map(h=>`
              <span class="evcc-chip ${h.cls}">${this.escapeHtml(h.text)}</span>
            `).join("")}
          </div>
        </div>

        <div class="evcc-review-job-grid">
          ${this._renderReviewKeyValue("Rooms",m)}
          ${this._renderReviewKeyValue("Scope",f)}
          ${this._renderReviewKeyValue("Profile",u,v)}
          ${this._renderReviewKeyValue("Used For Learning",e?.used_for_learning===!0?"Yes":"No")}
          ${this._renderReviewKeyValue("Primary Room",p)}
        </div>

        ${d?`
          <div class="evcc-review-job-note">${this.escapeHtml(d)}</div>
        `:""}

        <div class="evcc-review-job-actions">
          ${n?`
            ${this._renderReviewReasonChips(r,t,a)}
            <button
              type="button"
              class="evcc-chip"
              data-review-action="exclude"
              data-job-id="${this.escapeHtml(r)}"
              ${a?"disabled":""}
            >${a?"Working...":"Exclude"}</button>
          `:""}

          ${c?`
            <button
              type="button"
              class="evcc-chip"
              data-review-action="restore"
              data-job-id="${this.escapeHtml(r)}"
              ${a?"disabled":""}
            >${a?"Working...":"Restore"}</button>
          `:""}
        </div>
      </article>
    `},i._renderReviewKeyValue=function(e,t,r=""){return`
      <div class="evcc-review-kv">
        <div class="evcc-review-kv-label">${this.escapeHtml(e)}</div>
        <div class="evcc-review-kv-value">${this.escapeHtml(t)}</div>
        ${r?`<div class="evcc-review-kv-subtitle">${this.escapeHtml(r)}</div>`:""}
      </div>
    `},i._getSortedLearningReviewJobs=function(e,t){let r=Array.isArray(t)?[...t]:[],a=e.learningHistorySort?.()??"newest";return a==="outlier"?r.sort((n,c)=>Number(c?.outlier_score??0)-Number(n?.outlier_score??0)):a==="suggested"?r.filter(n=>n?.exclude_suggested===!0).sort((n,c)=>Number(c?.outlier_score??0)-Number(n?.outlier_score??0)):a==="excluded"?r.filter(n=>n?.excluded_from_learning===!0).sort((n,c)=>new Date(c?.started_at??0).getTime()-new Date(n?.started_at??0).getTime()):r.sort((n,c)=>new Date(c?.started_at??0).getTime()-new Date(n?.started_at??0).getTime())},i._formatReviewTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatReviewLabel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())}}function Rr(i){i.renderRoomsView=function(e){let{state:t}=e,r=t.getRoomsForActiveMap(),a=t.canStartCleaning(),n=t.startBlockedReason(),c=t.hasStartWarning(),s=t.enabledRoomCount(),o=t.activeJobRooms();return r.length===0?`
        <div class="evcc-rooms-view">
          <div class="evcc-empty">
            No rooms found. Run the discover rooms service to get started.
          </div>
        </div>
      `:`
      <div class="evcc-rooms-view">

        ${this.renderRoomsActionBar(a,n,s,r,c)}

        ${typeof this.renderLearningSummary=="function"?this.renderLearningSummary(t):""}

        ${typeof this.renderIncompleteRunBanner=="function"?this.renderIncompleteRunBanner(t):""}

        ${typeof this.renderLearningPreJobPanel=="function"?this.renderLearningPreJobPanel(t):""}

        ${typeof this.renderLearningLiveBanner=="function"?this.renderLearningLiveBanner(t):""}

        ${o?this.renderActiveJobSection(o):""}

        ${typeof this.renderLearningProgressList=="function"?this.renderLearningProgressList(t):""}

        ${this._renderOrphanedRoomsPanel(t)}

        <div class="evcc-rooms-workspace">
          <div class="evcc-rooms-main">

            ${this._renderRoomsViewToggle(t)}

            ${t.isMapViewActive?.()?typeof this.renderMapRoomView=="function"?this.renderMapRoomView(e):"":`<div class="evcc-room-grid">
                   ${r.map(l=>this.renderRoomCard(l,t)).join("")}
                 </div>`}
          </div>

          ${typeof this.renderRunProfilesPanel=="function"?this.renderRunProfilesPanel(t):""}
        </div>

      </div>
    `},i._renderRoomsViewToggle=function(e,t){let r=e.isMapViewActive?.()??!1;return`
      <div class="evcc-rooms-view-toggle">
        <button
          class="evcc-rooms-view-toggle-btn${r?"":" active"}"
          data-action="set-map-view"
          data-map-view="false"
          title="List view"
          aria-label="List view"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <line x1="5" y1="4" x2="13" y2="4"/>
            <line x1="5" y1="8" x2="13" y2="8"/>
            <line x1="5" y1="12" x2="13" y2="12"/>
            <circle cx="2.5" cy="4" r="1" fill="currentColor" stroke="none"/>
            <circle cx="2.5" cy="8" r="1" fill="currentColor" stroke="none"/>
            <circle cx="2.5" cy="12" r="1" fill="currentColor" stroke="none"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${r?" active":""}"
          data-action="set-map-view"
          data-map-view="true"
          title="Map view"
          aria-label="Map view"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="2" width="5" height="5" rx="1"/>
            <rect x="9" y="2" width="5" height="5" rx="1"/>
            <rect x="2" y="9" width="5" height="5" rx="1"/>
            <rect x="9" y="9" width="5" height="5" rx="1"/>
          </svg>
        </button>
        ${r?`
        <button
          class="evcc-rooms-view-toggle-btn evcc-rooms-view-toggle-btn--configure"
          data-action="open-map-config"
          title="Configure map"
          aria-label="Configure map"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="8" cy="8" r="2.5"/>
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
          </svg>
          Configure
        </button>
        <select
          class="evcc-rooms-animal-select"
          data-action="map-animal-select"
          title="Companion animal"
          aria-label="Companion animal"
        >
          ${["cat","dog","raccoon","parrot","snake"].map(a=>{let n=a.charAt(0).toUpperCase()+a.slice(1),c=e.mapAnimalSelection?.()??"cat";return`<option value="${a}"${c===a?" selected":""}>${n}</option>`}).join("")}
        </select>
        <input
          type="range"
          class="evcc-rooms-animal-scale"
          data-action="map-animal-scale"
          min="0.5" max="3" step="0.25"
          value="${e.mapAnimalScale?.()??1}"
          title="Icon size"
          aria-label="Icon size"
        >`:""}
      </div>
    `},i._renderOrphanedRoomsPanel=function(e){let t=e.orphanedRooms?.()??[];return t.length?`
      <div class="evcc-orphaned-rooms-panel">
        <span class="evcc-orphaned-rooms-label">Access not set</span>
        <div class="evcc-chips evcc-orphaned-rooms-chips">
          ${t.map(r=>`
            <span class="evcc-chip evcc-orphaned-rooms-chip">
              ${this.escapeHtml(r.name)}
            </span>
          `).join("")}
        </div>
      </div>
    `:""},i.renderActiveJobSection=function(e){let t=Array.isArray(e)?e:[];return t.length?`
      <div class="evcc-active-job">
        <div class="evcc-active-job-header">
          <span class="evcc-active-job-label">Running</span>
          <span class="evcc-active-job-pulse"></span>
        </div>

        <div class="evcc-queue-chips">
          ${t.map(r=>`
            <div class="evcc-queue-chip evcc-queue-chip--active">
              <span class="evcc-queue-chip-order">${this.escapeHtml(r.jobOrder??"")}</span>
              <span class="evcc-queue-chip-label">${this.escapeHtml(r.name??"")}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `:""},i.renderRoomsActionBar=function(e,t,r,a,n){let c=r===1?"1 room":`${r} rooms`,s=(Array.isArray(a)?a:[]).filter(A=>A.enabled),o=e?n?"evcc-chip--start-warn":"evcc-chip--start":"disabled",l=this.card?._state,d=!!l?.hasActiveRun?.(),u=Number(this.card?._learningController?.getJobProgressPercent?.()??0),v=Array.isArray(l?.learningRoomTimeline?.())?l.learningRoomTimeline():[],m=l?.learningCompletedRooms?.()||[],p=new Set(m.map(A=>String(A.room_id))),f=s.reduce((A,L)=>{let z=String(L.id),F=v.find(j=>String(j.room_id)===z),M=this.card?._state?.roomEstimateForRoom?.(L.id)??null,C=Number(F?.minutes??M?.minutes);return Number.isFinite(C)?A+C:A},0),h=Number(l?.dashboardPlannedJobEstimateTotalMinutes?.()),y=Number.isFinite(h)&&h>0?h:f,x=y>0?this._formatLearningDuration(y):null,w=l?.startConfirmation?.()??null,g=l?.startPreflight?.()??w?.preflight??null,R=!!l?.startRequiresConfirmation?.(),S=!!l?.cancelRunRequiresConfirmation?.(),P=!!l?.hasActiveRun?.(),O=!!l?.canPauseRun?.(),W=!!l?.canResumeRun?.(),ae=S?"Confirm Cancel":P?"Cancel Run":R?"Confirm Start":"Start Cleaning",oe=S?"evcc-chip--start-warn evcc-chip--confirm-flash":P?"evcc-chip--cancel-run":R?"evcc-chip--start-warn evcc-chip--confirm-flash":o,H=R||S,se=Array.isArray(g?.blocked_rooms)?g.blocked_rooms:[],X=Array.isArray(g?.modified_rooms)?g.modified_rooms:[],ie=Array.isArray(g?.warnings)?g.warnings:[];return`
    <div class="evcc-rooms-action-bar">

      <div class="evcc-rooms-bar-top">
        <div class="evcc-rooms-queue-summary">
          <span class="evcc-rooms-queue-count">${this.escapeHtml(c)}</span>
          <span class="evcc-rooms-queue-label">included</span>
          ${x?`
            <span class="evcc-rooms-queue-label">\xB7 ~${this.escapeHtml(x)}</span>
          `:""}
        </div>

        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${oe}"
            data-action="primary-room-action"
            ${!P&&!R&&!e?"disabled":""}
            title="${this.escapeHtml(t??"")}"
          >${this.escapeHtml(ae)}</button>

          ${P&&(O||W)?`
            <button
              type="button"
              class="evcc-chip"
              data-action="${W?"resume-run":"pause-run"}"
            >${W?"Resume":"Pause"}</button>
          `:""}

          <button type="button" class="evcc-chip" data-action="locate-vacuum">
            Locate
          </button>

          <button type="button" class="evcc-chip" data-action="select-all">
            Select All
          </button>

          <button type="button" class="evcc-chip" data-action="clear-queue">
            Clear Queue
          </button>
        </div>
      </div>

      ${t&&!e?`
        <div class="evcc-rooms-block-reason">${this.escapeHtml(t)}</div>
      `:""}

      ${H?`
        <div class="evcc-rooms-inline-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="cancel-primary-confirmation"
          >Cancel</button>
        </div>
      `:""}

      ${R?`
        <div class="evcc-start-preflight-panel">
          <div class="evcc-start-preflight-header">Reduced Run Detected</div>

          <div class="evcc-start-preflight-summary">
            <span>${this.escapeHtml(String(g?.blocked_room_count??0))} blocked</span>
            <span>\xB7</span>
            <span>${this.escapeHtml(String(g?.included_room_count??r))} included</span>
            ${Number.isFinite(Number(g?.blocked_expected_minutes))&&Number(g?.blocked_expected_minutes)>0?`
              <span>\xB7</span>
              <span>~${this.escapeHtml(this._formatLearningDuration(Number(g.blocked_expected_minutes)))} skipped</span>
            `:""}
          </div>

          ${se.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Blocked Rooms</div>
              <div class="evcc-start-preflight-list">
                ${se.map(A=>`
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-room">${this.escapeHtml(A.name??A.room_id??"Room")}</span>
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(A.reason??"Blocked")}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          `:""}

          ${X.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Modified Rooms</div>
              <div class="evcc-start-preflight-list">
                ${X.map(A=>`
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-room">${this.escapeHtml(A.name??A.room_id??"Room")}</span>
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(Object.keys(A.changes??{}).join(", ")||"Settings adjusted")}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          `:""}

          ${ie.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Warnings</div>
              <div class="evcc-start-preflight-list">
                ${ie.map(A=>`
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(A)}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          `:""}
        </div>
      `:""}

      ${s.length>0?`
        <div class="evcc-queue-chips">

          ${s.map((A,L)=>{let z=String(A.id),F=v.find(ne=>String(ne.room_id)===z),M=p.has(z),C=this.card?._learningController?.getRoomProgressSnapshot?.(A.id)??null,j="evcc-queue-chip--queued";d&&(F?.completed||M||C?.isCompleted?j="evcc-queue-chip--completed":F?.current||C?.isCurrent?j="evcc-queue-chip--current":(F?.remaining||F)&&(j="evcc-queue-chip--remaining"));let V="";if(F?.confidence_breakpoint?.ui_variant){let ne=F.confidence_breakpoint.ui_variant;ne==="success"?V="evcc-queue-chip--confidence-high":ne==="warning"?V="evcc-queue-chip--confidence-medium":ne==="error"&&(V="evcc-queue-chip--confidence-low")}let le=F?.minutes!=null?this._formatLearningMinutes(F.minutes):null,U=j==="evcc-queue-chip--completed"?100:j==="evcc-queue-chip--current"?Number(C?.percent??u):0,ue=j==="evcc-queue-chip--current"?`${Math.max(0,Math.min(99,Math.floor(U)))}%`:le;return`
              <button
                type="button"
                class="evcc-queue-chip ${j} ${V}"
                data-queue-chip="true"
                data-room-id="${A.id}"
                data-map-id="${this.escapeHtml(A.mapId)}"
                data-enabled="${A.enabled?"true":"false"}"
                style="--job-progress:${U}%;"
                title="Click for settings \xB7 Double-click for estimate \xB7 Hold to remove from queue"
                aria-label="Queue room ${this.escapeHtml(A.name)}"
              >
                <span class="evcc-queue-chip-order">${L+1}</span>

                <span class="evcc-queue-chip-label">
                  ${this.escapeHtml(A.name)}
                </span>

                ${ue?`
                  <span class="evcc-queue-chip-time">
                    ${this.escapeHtml(ue)}
                  </span>
                `:""}

              </button>
            `}).join("")}

        </div>
      `:`
        <div class="evcc-queue-empty">
          No rooms queued \u2014 toggle rooms to include them
        </div>
      `}

    </div>
  `},i.renderRoomCard=function(e,t){let r=this._normalizeRoomDisplayData(e),a=r.cleanMode?r.cleanModeLabel||this._formatCleanMode(r.cleanMode):null,c=!r.fanSpeed||["off","normal"].includes(String(r.fanSpeed).toLowerCase())?null:r.fanSpeedLabel||this._formatFanSpeed(r.fanSpeed),o=!r.cleanIntensity||String(r.cleanIntensity).toLowerCase()==="standard"?null:r.cleanIntensityLabel||this._formatCleanIntensity(r.cleanIntensity),l=this._isMopMode(r.cleanMode)&&r.waterLevel&&String(r.waterLevel).toLowerCase()!=="off"?r.waterLevelLabel||this._formatWaterLevel(r.waterLevel):null,d=this._isMopMode(r.cleanMode)&&r.edgeMopping?"Edge Mop On":null,u=Number(r.cleanPasses)>1?`${Number(r.cleanPasses)}\xD7 passes`:null,v=this.card?._state?.orderDragItemId?.(),m=this.card?._state?.orderDragOverItemId?.(),p=String(v)===String(r.id)?"evcc-order-drag-source":"",f=String(m)===String(r.id)?"evcc-order-drag-target":"",h=t?.roomEstimateForRoom?.(r.id)??null,y=t?.dashboardPlannedWaterRoomForRoom?.(r.id,r.slug)??null,x="";if(h&&h.error==null){let L=h.source==="learned"?"evcc-room-status--estimate-learned":"evcc-room-status--estimate-default",z=h.source==="learned"?this._formatLearningMinutes(h.minutes):`~${this._formatLearningMinutes(h.minutes)}`,F=[`Estimate: ${this._formatLearningMinutes(h.minutes)}`];h.source&&F.push(`Source: ${String(h.source)}`);let M=Number(h.battery);Number.isFinite(M)&&F.push(`Battery: ${M}`);let C=F.join(" \xB7 ");x=`
      <div
        class="evcc-room-status evcc-room-status--estimate ${L}"
        title="${this.escapeHtml(C)}"
      >
        ${this.escapeHtml(z)}
      </div>
    `}let w="",g="",R="";if(h&&h.error==null&&typeof this.renderConfidenceChip=="function")if(h.source==="learned"){let L=h?.confidence_breakpoint?.ui_variant,z=L==="success"?"Reliable":L==="warning"?"Learning":L==="error"?"Uncertain":null;z&&(w=this.renderConfidenceChip(h.confidence_breakpoint,z,z),L==="success"?g="evcc-room-card--confidence-high":L==="warning"?g="evcc-room-card--confidence-medium":g="evcc-room-card--confidence-low")}else h.source==="default"&&(w=this.renderConfidenceChip({ui_variant:"neutral"},"Unlearned","Unlearned"));let S=String(y?.effective_clean_mode??y?.clean_mode??"").toLowerCase(),P=String(y?.effective_water_level??y?.water_level??"").toLowerCase();if(!!(y?.mop_active||this._isMopMode(S))&&P!=="off"){let L=Number(y.estimated_robot_water_used_ml);Number.isFinite(L)&&(R=`
        <div
          class="evcc-room-status"
          title="${this.escapeHtml([`Projected water use: ~${Math.round(L)} ml`,y?.clean_mode_label?`Mode: ${String(y.clean_mode_label)}`:y?.effective_clean_mode?`Mode: ${String(y.effective_clean_mode)}`:null,y?.water_level_label?`Water: ${String(y.water_level_label)}`:y?.effective_water_level?`Water: ${String(y.effective_water_level)}`:null].filter(Boolean).join(" \xB7 "))}"
        >
          ${this.escapeHtml(`~${Math.round(L)} ml water`)}
        </div>
      `)}let W=[];h?.intensity_mismatch&&W.push({text:"\u26A0 intensity mismatch",variant:"warning"});let ae=t?.troubleRoomForRoom?.(r.id)??null;if(ae?.is_trouble){let L=Number(ae.miss_count??0),z=Number(ae.run_count??0),F=Number(ae.miss_rate??0),M=Number.isFinite(F)?Math.round(F*100):null;W.push({text:`\u26A0 Missed ${L}\xD7 of ${z} run${z===1?"":"s"}${M!==null?` (${M}%)`:""}`,variant:"warning",title:`This room was missed in ${M??"?"}% of recent runs. Consider checking for obstacles or map accuracy.`})}let oe=!!this.card?._state?.hasActiveRun?.(),H=this.card?._learningController?.getRoomProgressSnapshot?.(r.id)??null,se=H?.percent??this.card?._learningController?.getRoomProgressPercent?.(r.id),X=Number.isFinite(se)?se:0,ie="evcc-room-card--queue-idle";r.enabled&&oe&&(H?.isCompleted||X>=100?ie="evcc-room-card--queue-completed":H?.isCurrent||X>0?ie="evcc-room-card--queue-current":ie="evcc-room-card--queue-remaining");let A=oe&&H&&H.isCurrent?`
        <div class="evcc-room-progress-meta">
          <div
            class="evcc-room-status evcc-room-progress-chip"
            title="${this.escapeHtml([`Progress: ${H.percent}%`,Number.isFinite(H.elapsedMinutes)?`Elapsed: ${this._formatLearningMinutes(H.elapsedMinutes)}`:"",Number.isFinite(H.remainingMinutes)?`Remaining: ${this._formatLearningMinutes(H.remainingMinutes)}`:""].filter(Boolean).join(" \xB7 "))}"
          >
            ${this.escapeHtml(`${H.percent}% complete`)}
          </div>

          ${Number.isFinite(H.remainingMinutes)?`
            <div
              class="evcc-room-status evcc-room-progress-chip evcc-room-progress-chip--remaining"
              title="${this.escapeHtml([`Progress: ${H.percent}%`,Number.isFinite(H.elapsedMinutes)?`Elapsed: ${this._formatLearningMinutes(H.elapsedMinutes)}`:"",`Remaining: ${this._formatLearningMinutes(H.remainingMinutes)}`].filter(Boolean).join(" \xB7 "))}"
            >
              ${this.escapeHtml(`~${this._formatLearningMinutes(H.remainingMinutes)} left`)}
            </div>
          `:""}
        </div>
      `:"";return`
    <div
      class="evcc-room-card ${r.enabled?"is-enabled":"is-disabled"} ${p} ${f} ${ie} ${g}"
      data-room-card-toggle="true"
      data-room-id="${r.id}"
      data-map-id="${this.escapeHtml(r.mapId)}"
      data-enabled="${r.enabled?"true":"false"}"
      data-order-drop-target
      data-scope="rooms"
      data-item-id="${r.id}"
      role="button"
      tabindex="0"
      aria-pressed="${r.enabled?"true":"false"}"
      aria-label="${this.escapeHtml(`${r.enabled?"Exclude":"Include"} room ${r.name}`)}"
      style="--room-progress:${X}%;"
    >

      ${typeof this._renderFloorTextureLayer=="function"?this._renderFloorTextureLayer(r):""}

      <div class="evcc-room-row evcc-room-row-1">
        <div class="evcc-room-controls">

          <div class="evcc-order-controls">
            <span class="evcc-order-chip">#${this.escapeHtml(r.order)}</span>

            <button
              type="button"
              class="evcc-chip evcc-order-move-button"
              data-action="open-order-selector"
              data-scope="rooms"
              data-item-id="${r.id}"
              title="Move room"
            >Move</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--icon evcc-order-drag-handle"
              data-order-drag-item
              data-scope="rooms"
              data-item-id="${r.id}"
              draggable="true"
              title="Drag to reorder"
            >\u22EE\u22EE</button>
          </div>

          <button
            type="button"
            class="evcc-room-settings-hit-target"
            data-action="open-room-settings"
            data-room-id="${r.id}"
            data-map-id="${this.escapeHtml(r.mapId)}"
            title="Room settings"
            aria-label="Open room settings for ${this.escapeHtml(r.name)}"
          >
            <span class="evcc-chip evcc-chip--icon evcc-room-settings-button">\u2699</span>
          </button>
        </div>
      </div>

      <div class="evcc-room-row evcc-room-row-2">
        <div class="evcc-room-name">${this.escapeHtml(r.name)}</div>
      </div>

      ${a||c||o||l||d||u?`
        <div class="evcc-room-setting-chips">
          ${a?`<span class="evcc-room-setting-chip">${this.escapeHtml(a)}</span>`:""}
          ${c?`<span class="evcc-room-setting-chip">${this.escapeHtml(c)}</span>`:""}
          ${o?`<span class="evcc-room-setting-chip">${this.escapeHtml(o)}</span>`:""}
          ${l?`<span class="evcc-room-setting-chip">${this.escapeHtml(l)}</span>`:""}
          ${d?`<span class="evcc-room-setting-chip">${this.escapeHtml(d)}</span>`:""}
          ${u?`<span class="evcc-room-setting-chip">${this.escapeHtml(u)}</span>`:""}
        </div>
      `:""}

      ${A}

      <div class="evcc-room-chip-row">

        ${x}

        ${w}

        ${R}

      </div>

      ${W.length?`
        <div class="evcc-room-notes">
          ${W.map(L=>`
            <div
              class="evcc-room-note evcc-room-note--${this.escapeHtml(L.variant)}"
              ${(()=>{let z=String(L.text).includes("No learned data")?"This room is using a fallback estimate until enough learned samples are collected.":String(L.text).includes("runs to reliable")?`Estimated ${String(L.text).split(" ")[0]} more runs to reach high confidence.`:String(L.text).includes("intensity mismatch")?"Estimate was learned from a different cleaning intensity or profile.":"",F=L.title||z;return F?`title="${this.escapeHtml(F)}"`:""})()}
            >
              ${this.escapeHtml(L.text)}
            </div>
          `).join("")}
        </div>
      `:""}

    </div>
  `},i._normalizeRoomDisplayData=function(e){let t=e?.selected_profile_details??{},r=String(e?.profile_name??e?.profileName??e?.profile??"vacuum_quick"),a=String(e?.clean_mode??e?.cleanMode??t?.clean_mode??"vacuum"),n=String(e?.fan_speed??e?.fanSpeed??t?.fan_speed??""),c=String(e?.water_level??e?.waterLevel??t?.water_level??""),s=String(e?.clean_intensity??e?.cleanIntensity??t?.clean_intensity??""),o=Number(e?.clean_passes??e?.cleanPasses??e?.passes??t?.default_clean_passes??1),l=!!(e?.edge_mopping??e?.edgeMopping??t?.default_edge_mopping??!1),d=String(e?.floor_type??e?.floorType??""),u=String(e?.carpet_type??e?.carpetType??""),v=!!(e?.carpet??(()=>{let p=String(d).toLowerCase();return p==="carpet"||p.startsWith("carpet_")||p.startsWith("carpet-")})()),m=Number(e?.order??e?.displayOrder??e?.position??999999);return{id:e?.id,mapId:e?.mapId??e?.map_id??"",name:e?.name??e?.room_name??"",slug:e?.slug??e?.room_slug??null,enabled:!!e?.enabled,order:Number.isFinite(m)?m:999999,profileName:r,profileLabel:e?.profile_label??e?.profileLabel??e?.selected_profile_label??e?.resolved_profile_label??null,profileSubtitle:e?.profile_subtitle??e?.profileSubtitle??null,isCustomProfile:r.toLowerCase()==="custom",cleanMode:a,cleanModeLabel:e?.clean_mode_label??e?.cleanModeLabel??t?.clean_mode_label??null,fanSpeed:n,fanSpeedLabel:e?.fan_speed_label??e?.fanSpeedLabel??t?.fan_speed_label??null,waterLevel:c,waterLevelLabel:e?.water_level_label??e?.waterLevelLabel??t?.water_level_label??null,cleanIntensity:s,cleanIntensityLabel:e?.clean_intensity_label??e?.cleanIntensityLabel??t?.clean_intensity_label??t?.path_type_label??null,cleanPasses:Number.isFinite(o)?o:1,cleanPassesLabel:e?.clean_passes_label??e?.cleanPassesLabel??t?.clean_passes_label??null,edgeMopping:l,edgeMoppingLabel:e?.edge_mopping_label??e?.edgeMoppingLabel??t?.edge_mopping_label??null,floorType:d,floorTypeLabel:e?.floor_type_label??e?.floorTypeLabel??null,carpetType:u,carpetTypeLabel:e?.carpet_type_label??e?.carpetTypeLabel??null,carpet:v,selectedProfileDetails:t}},i._isMopMode=function(e){let t=String(e??"").toLowerCase();return t==="mop"||t==="vacuum_mop"||t.includes("mop")||t.includes("wash")},i._roomProfileLabel=function(e){let t=String(e??"").trim();return t?t.toLowerCase()==="custom"?"Custom":t==="vacuum_quick"?"Vacuum Only Quick":t==="vacuum_deep"?"Vacuum Only Deep":t==="vacuum_mop_quick"?"Quick":t==="vacuum_mop_deep"?"Deep":t==="user_1"?"User Profile 1":t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Standard"},i._formatCleanMode=function(e){let t=String(e??"").trim().toLowerCase();return t==="vacuum_mop"||t==="vacuum and mop"?"Vacuum + Mop":t==="vacuum"?"Vacuum":t==="mop"?"Mop":this._formatSettingValue(e)},i._formatFanSpeed=function(e){return this._formatSettingValue(e)},i._formatWaterLevel=function(e){return this._formatSettingValue(e)},i._formatCleanIntensity=function(e){return this._formatSettingValue(e)},i._formatFloorType=function(e){return this._formatSettingValue(e)},i._formatSettingValue=function(e){return e?String(e).replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase()):""}}function Er(i){i.renderRunProfilesPanel=function(e){let t=e.savedRunProfiles?.()??[],r=e.selectedRunProfile?.()??null,a=e.runProfileDraft?.()??{name:"",expose_as_button:!1},n=!!e.isRunProfileEditorOpen?.(),c=e.runProfileEditorMode?.()??"new";return`
      <aside class="evcc-run-profiles-panel">
        <div class="evcc-run-profiles-panel-header">
          <div>
            <div class="evcc-run-profiles-title">Run Profiles</div>
            <div class="evcc-run-profiles-subtitle">
              Save this room setup and reapply it later without rebuilding the queue by hand.
            </div>
          </div>

          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="open-new-run-profile"
          >Save This Setup</button>
        </div>

        ${n?`
          <div class="evcc-run-profiles-editor">
            <div class="evcc-run-profiles-editor-title">
              ${c==="edit"?"Edit Saved Profile":"Create Run Profile"}
            </div>

            <label class="evcc-run-profiles-field">
              <span class="evcc-run-profiles-label">Name</span>
              <input
                type="text"
                class="evcc-run-profiles-input"
                value="${this.escapeHtml(a.name??"")}"
                placeholder="Morning Clean"
                data-run-profile-field="name"
              />
            </label>

            <label class="evcc-run-profiles-toggle">
              <input
                type="checkbox"
                ${a.expose_as_button?"checked":""}
                data-run-profile-field="expose_as_button"
              />
              <span>Expose as Home Assistant Button</span>
            </label>

            <div class="evcc-run-profiles-editor-actions">
              <button
                type="button"
                class="evcc-chip evcc-chip--save"
                data-action="${c==="edit"?"overwrite-run-profile":"save-new-run-profile"}"
              >${c==="edit"?"Save Over Profile":"Create Profile"}</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="cancel-run-profile-editor"
              >Cancel</button>
            </div>
          </div>
        `:""}

        ${t.length?`
          <div class="evcc-run-profiles-list">
            ${t.map(s=>`
              <button
                type="button"
                class="evcc-chip ${r?.id===s.id?"active":""}"
                data-action="apply-run-profile"
                data-profile-id="${this.escapeHtml(s.id)}"
                title="${this.escapeHtml(s.summary||s.room_names_label||s.name)}"
              >${this.escapeHtml(s.name)}</button>
            `).join("")}
          </div>
        `:`
          <div class="evcc-run-profiles-empty">
            No saved profiles yet.
          </div>
        `}

        ${r?`
          <div class="evcc-run-profiles-selected">
            <div class="evcc-run-profiles-selected-name">
              ${this.escapeHtml(r.name)}
            </div>

            <div class="evcc-run-profiles-selected-meta">
              <span>${this.escapeHtml(String(r.room_count||r.room_ids?.length||0))} rooms</span>
              ${r.expose_as_button?"<span>\xB7 Exposed as button</span>":""}
            </div>

            ${r.summary?`
              <div class="evcc-run-profiles-selected-summary">
                ${this.escapeHtml(r.summary)}
              </div>
            `:r.room_names_label?`
              <div class="evcc-run-profiles-selected-summary">
                ${this.escapeHtml(r.room_names_label)}
              </div>
            `:""}

            <div class="evcc-run-profiles-selected-actions">
              <button
                type="button"
                class="evcc-chip"
                data-action="edit-run-profile"
                data-profile-id="${this.escapeHtml(r.id)}"
              >Edit</button>

              <button
                type="button"
                class="evcc-chip"
                data-action="delete-run-profile"
                data-profile-id="${this.escapeHtml(r.id)}"
              >Delete</button>
            </div>
          </div>
        `:""}
      </aside>
    `}}function kr(i){i.renderMaintenanceView=function(e){let{state:t}=e,r=t.dashboardUpkeep?.()??{},a=r.attention_summary??t.dashboardAttentionSummary?.(),n=t.dashboardStatusSummary?.(),c=r.model_meta??{},s=Array.isArray(r.replacement_items)?r.replacement_items:[],o=Array.isArray(r.maintenance_items)?r.maintenance_items:[],l=Number(r.attention_count??0),d=r.highest_priority_status_label??r.highest_priority_status??null,u=r.updated_at??null,v=t.maintenanceActiveTab?.()??"maintenance_items",m=v==="replacements"?s:o,p=v==="replacements"?"Replacement Items":"Maintenance Items",f=v==="replacements"?"Upstream replacement-style items":"Integration-managed maintenance intervals",h=[...o.map(O=>({...O,_category:"Maintenance"})),...s.map(O=>({...O,_category:"Replacement"}))].filter(O=>this._maintenanceItemNeedsAttention(O)),y=r.station_water??null,w=(t.dashboardPlannedWaterEstimate?.()??null)?.available_clean_tank_ml??null,g=c.name??null,R=c.guide_family_name??null,S=s.filter(O=>this._maintenanceItemNeedsAttention(O)).length,P=o.filter(O=>this._maintenanceItemNeedsAttention(O)).length;return`
      <div class="evcc-maintenance-view">
        <div class="evcc-maintenance-grid">

          <section class="evcc-maintenance-panel">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Maintenance Overview</div>
                <div class="evcc-maintenance-panel-subtitle">
                  ${this.escapeHtml(a||n||"Backend maintenance snapshot")}
                </div>
              </div>
              ${R?`
                <div class="evcc-maintenance-meta-badge">
                  ${this.escapeHtml(R)}
                </div>
              `:""}
            </div>

            ${g||u?`
              <div class="evcc-maintenance-model-line">
                ${this.escapeHtml(g??"")}
                ${g&&u?" \xB7 ":""}
                ${u?`Updated ${this.escapeHtml(this._formatMaintenanceTimestamp(u))}`:""}
              </div>
            `:""}

            <div class="evcc-maintenance-stats">
              ${this._renderMaintenanceStat("Attention",l)}
              ${this._renderMaintenanceStat("Priority",d||"Normal")}
              ${this._renderMaintenanceStat("Items",o.length)}
              ${this._renderMaintenanceStat("Water",r.station_water_label??y??"Unknown")}
            </div>
          </section>

          <section class="evcc-maintenance-panel">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Replacement Overview</div>
                <div class="evcc-maintenance-panel-subtitle">
                  Replacement inventory and lifecycle snapshot
                </div>
              </div>
            </div>

            <div class="evcc-maintenance-stats">
              ${this._renderMaintenanceStat("Items",s.length)}
              ${this._renderMaintenanceStat("Attention",S)}
              ${this._renderMaintenanceStat("Healthy",Math.max(s.length-S,0))}
              ${this._renderMaintenanceStat("Status",s.length?"Tracked":"Empty")}
            </div>
          </section>

          <section class="evcc-maintenance-panel evcc-maintenance-panel--wide">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Needs Attention</div>
                <div class="evcc-maintenance-panel-subtitle">
                  ${this.escapeHtml(h.length?"Items currently flagged for service or replacement attention":"No maintenance or replacement items currently need attention")}
                </div>
              </div>
            </div>

            ${h.length?`<div class="evcc-maintenance-list">
                  ${h.map(O=>this._renderMaintenanceAttentionItem(O)).join("")}
                 </div>`:'<div class="evcc-maintenance-empty">Everything currently looks healthy.</div>'}
          </section>

          <section class="evcc-maintenance-panel evcc-maintenance-panel--wide">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Items</div>
                <div class="evcc-maintenance-panel-subtitle">
                  Switch between maintenance intervals and replacement items
                </div>
              </div>
            </div>

            <div class="evcc-maintenance-tabs" role="tablist" aria-label="Maintenance item groups">
              <button
                type="button"
                class="evcc-chip evcc-maintenance-tab ${v==="maintenance_items"?"active":""}"
                data-maintenance-tab="maintenance_items"
                role="tab"
                aria-selected="${v==="maintenance_items"?"true":"false"}"
              >
                Maintenance Items
              </button>

              <button
                type="button"
                class="evcc-chip evcc-maintenance-tab ${v==="replacements"?"active":""}"
                data-maintenance-tab="replacements"
                role="tab"
                aria-selected="${v==="replacements"?"true":"false"}"
              >
                Replacements
              </button>
            </div>

            <div class="evcc-maintenance-tab-panel">
              <div class="evcc-maintenance-tab-header">
                <div class="evcc-maintenance-panel-title">${this.escapeHtml(p)}</div>
                <div class="evcc-maintenance-panel-subtitle">${this.escapeHtml(f)}</div>
              </div>

              ${m.length?`<div class="evcc-maintenance-card-grid">
                    ${m.map(O=>this._renderMaintenanceCard(O)).join("")}
                    ${v==="maintenance_items"?this._renderStationWaterCard(y,w,r.station_water_label):""}
                   </div>`:`<div class="evcc-maintenance-empty">No ${v==="replacements"?"replacement":"maintenance"} items reported.</div>`}
            </div>
          </section>

        </div>
      </div>
    `},i._renderMaintenanceStat=function(e,t){return`
      <div class="evcc-maintenance-stat">
        <div class="evcc-maintenance-stat-value">${this.escapeHtml(t)}</div>
        <div class="evcc-maintenance-stat-label">${this.escapeHtml(e)}</div>
      </div>
    `},i._renderMaintenanceAttentionItem=function(e){let t=e?.label??e?.component_label??e?.name??e?.title??"Unnamed item",r=e?.status_label??this._formatMaintenanceStatus(e?.status??"warning"),a=e?.remaining_summary??e?.usage_summary??e?.summary??e?.message??e?.description??e?.detail??"";return`
      <button
        type="button"
        class="evcc-maintenance-item"
        data-action="open-maintenance-modal"
        data-item-kind="${this.escapeHtml(String(e?.kind??""))}"
        data-item-component="${this.escapeHtml(String(e?.component??""))}"
        data-item-entity-id="${this.escapeHtml(String(e?.entity_id??""))}"
      >
        <div class="evcc-maintenance-item-main">
          <div class="evcc-maintenance-item-name">${this.escapeHtml(t)}</div>
          <div class="evcc-maintenance-item-detail">
            ${this.escapeHtml([e?._category,a].filter(Boolean).join(" \xB7 "))}
          </div>
        </div>
        <div class="evcc-maintenance-item-side">${this.escapeHtml(r)}</div>
      </button>
    `},i._renderMaintenanceCard=function(e){let t=e?.label??e?.component_label??e?.name??e?.title??"Unnamed item",r=String(e?.kind??"maintenance"),a=String(e?.status??"unknown"),n=e?.status_label??this._formatMaintenanceStatus(a),c=e?.available!==!1,s=this._maintenanceRemainingPercent(e),o=Number.isFinite(s)?Math.max(0,Math.min(100,s)):0,l=this._maintenancePrimaryValue(e),d=this._maintenanceSecondaryValue(e),u=e?.guide?.display??null,v=u?.frequency||this._formatMaintenanceFrequency(u?.frequency);return`
      <button
        type="button"
        class="evcc-maintenance-card evcc-maintenance-card--status-${this.escapeHtml(a)} ${c?"":"evcc-maintenance-card--unavailable"}"
        data-action="open-maintenance-modal"
        data-item-kind="${this.escapeHtml(r)}"
        data-item-component="${this.escapeHtml(String(e?.component??""))}"
        data-item-entity-id="${this.escapeHtml(String(e?.entity_id??""))}"
        style="--maintenance-remaining:${o}%;"
      >
        <div class="evcc-maintenance-card-header">
          <div class="evcc-maintenance-card-title">${this.escapeHtml(t)}</div>
          <div class="evcc-maintenance-card-status">${this.escapeHtml(n)}</div>
        </div>

        <div class="evcc-maintenance-card-value">
          ${this.escapeHtml(l)}
        </div>

        <div class="evcc-maintenance-card-detail">
          ${this.escapeHtml([e?.kind_label??this._formatMaintenanceKind(r),d].filter(Boolean).join(" | "))}
        </div>

        ${v?`
          <div class="evcc-maintenance-card-secondary">
            ${this.escapeHtml(v)}
          </div>
        `:""}
      </button>
    `},i._renderStationWaterCard=function(e,t=null,r=null){let a=e!=null&&e!=="",n=Number(e),c=Number.isFinite(n),s=String(r??"").trim()||(a?c?`${Math.round(n)}%`:String(e):"Unknown"),o=String(s).trim().toLowerCase(),l="unknown";c?n>=70?l="good":n>=35?l="warning":n>0?l="replace_soon":l="replace_now":["full","high","good","ok","normal"].includes(o)?l="good":["medium","mid"].includes(o)?l="warning":["low","empty","none"].includes(o)&&(l="replace_soon");let d=c?n>=70?"High":n>=35?"Medium":n>0?"Low":"Empty":String(r??"").trim()||this._formatMaintenanceStatus(l),u=c?Math.max(0,Math.min(100,n)):l==="good"?100:l==="warning"?55:l==="replace_soon"?20:0;return`
      <article
        class="evcc-maintenance-card evcc-maintenance-card--status-${this.escapeHtml(l)}"
        style="--maintenance-remaining:${u}%;"
      >
        <div class="evcc-maintenance-card-header">
          <div class="evcc-maintenance-card-title">Station Water</div>
          <div class="evcc-maintenance-card-status">${this.escapeHtml(d)}</div>
        </div>

        <div class="evcc-maintenance-card-value">
          ${this.escapeHtml(s)}
        </div>

        <div class="evcc-maintenance-card-detail">
          Base station water reservoir status
        </div>

        ${Number.isFinite(Number(t))?`
          <div class="evcc-maintenance-card-secondary">
            ~${this.escapeHtml(String(Math.round(Number(t))))} ml remaining
          </div>
        `:""}
      </article>
    `},i.renderMaintenanceItemModal=function(e){let t=e?.state,r=t?.activeMaintenanceModalItem?.();if(!r)return"";let a=r?.label??r?.component_label??r?.name??r?.title??"Item details",n=String(r?.kind??"maintenance"),c=String(r?.status??"unknown"),s=r?.status_label??this._formatMaintenanceStatus(c),o=this._maintenancePrimaryValue(r),l=this._maintenanceSecondaryValue(r),d=r?.guide?.display??null,u=Array.isArray(d?.steps)?d.steps.filter(Boolean):[],v=Array.isArray(d?.notes)?d.notes.filter(Boolean):[],m=t?.maintenanceResetUi?.()??{},p=t?.canInvokeMaintenanceReset?.(r)??!1,f=String(r?.reset_kind??"").trim().toLowerCase(),h=!!m?.pending,y=!!m?.confirming,x=String(m?.success??""),w=String(m?.error??"");return`
      <div class="evcc-modal-backdrop" data-action="close-maintenance-modal">
        <div class="evcc-modal evcc-maintenance-modal" data-stop-propagation>
          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.escapeHtml(a)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-maintenance-modal"
              title="Close"
            >X</button>
          </div>

          <div class="evcc-modal-body">
            <div class="evcc-maintenance-modal-hero evcc-maintenance-modal-hero--status-${this.escapeHtml(c)}">
              <div class="evcc-maintenance-modal-hero-top">
                <div class="evcc-maintenance-modal-hero-label">${this.escapeHtml(r?.kind_label??this._formatMaintenanceKind(n))}</div>
                <div class="evcc-maintenance-modal-hero-status">${this.escapeHtml(s)}</div>
              </div>

              <div class="evcc-maintenance-modal-hero-value">${this.escapeHtml(o)}</div>

              ${l?`
                <div class="evcc-maintenance-modal-hero-detail">${this.escapeHtml(l)}</div>
              `:""}
            </div>

            ${u.length?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Steps</div>
                <ol class="evcc-maintenance-guide-list">
                  ${u.map(g=>`
                    <li class="evcc-maintenance-guide-item">${this.escapeHtml(g)}</li>
                  `).join("")}
                </ol>
              </div>
            `:`
              <div class="evcc-maintenance-empty">No model-aware steps were provided for this item.</div>
            `}

            ${v.length?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Notes</div>
                <div class="evcc-maintenance-guide-notes">
                  ${v.map(g=>`
                    <div class="evcc-maintenance-guide-note">${this.escapeHtml(g)}</div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${p?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Reset</div>

                ${x?`
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--success">
                    ${this.escapeHtml(x)}
                  </div>
                `:""}

                ${w?`
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--error">
                    ${this.escapeHtml(w)}
                  </div>
                `:""}

                ${y?`
                  <div class="evcc-maintenance-reset-hint">
                    ${this.escapeHtml(f==="integration"?`This will reset the tracked maintenance interval for ${a}.`:`This will send the reset command to the device for ${a}.`)}
                  </div>

                  <div class="evcc-maintenance-reset-actions">
                    <button
                      type="button"
                      class="evcc-chip"
                      data-action="cancel-maintenance-reset"
                      ${h?"disabled":""}
                    >Cancel</button>

                    <button
                      type="button"
                      class="evcc-chip evcc-chip--save"
                      data-action="confirm-maintenance-reset"
                      ${h?"disabled":""}
                    >${h?"Resetting...":"Confirm Reset"}</button>
                  </div>
                `:`
                  <div class="evcc-maintenance-reset-actions">
                    <button
                      type="button"
                      class="evcc-chip"
                      data-action="begin-maintenance-reset"
                      title="${this.escapeHtml(f==="integration"?"Reset this tracked maintenance interval and refresh the dashboard snapshot.":"Send the reset command to the device for this replacement item.")}"
                      ${h?"disabled":""}
                    >Reset</button>
                  </div>
                `}
              </div>
            `:""}
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-maintenance-modal"
            >Close</button>
          </div>
        </div>
      </div>
    `},i._maintenanceItemNeedsAttention=function(e){if(!e||typeof e!="object")return!1;if(e.needs_attention===!0||e.attention_required===!0||e.warning===!0||e.overdue===!0||e.due===!0)return!0;let t=String(e?.status??"").trim().toLowerCase();if(["warning","replace_soon","replace_now"].includes(t))return!0;let r=Number(e.remaining_percent);return!!(Number.isFinite(r)&&r<=20)},i._maintenanceRemainingPercent=function(e){let t=Number(e?.remaining_percent);if(Number.isFinite(t))return t;let r=Number(e?.remaining_hours),a=Number(e?.kind==="replacement"?e?.max_life_hours??e?.total_life_hours:e?.interval_hours);return Number.isFinite(r)&&Number.isFinite(a)&&a>0?r/a*100:null},i._maintenancePrimaryValue=function(e){let t=String(e?.remaining_summary??"").trim();if(t)return t;let r=this._maintenanceRemainingPercent(e);if(Number.isFinite(r))return`${Math.round(r)}% remaining`;let a=Number(e?.remaining_hours);if(Number.isFinite(a))return`${this._formatMaintenanceHours(a)} remaining`;let n=e?.remaining_value,c=e?.remaining_unit;return n!=null?[n,c].filter(Boolean).join(" "):"Unknown remaining life"},i._maintenanceSecondaryValue=function(e){let t=String(e?.usage_summary??"").trim();if(t)return t;if(e?.kind==="replacement"){let c=Number(e?.usage_hours),s=Number(e?.max_life_hours??e?.total_life_hours);if(Number.isFinite(c)&&Number.isFinite(s))return`${this._formatMaintenanceHours(c)} used of ${this._formatMaintenanceHours(s)}`}let r=Number(e?.remaining_hours),a=Number(e?.interval_hours);if(Number.isFinite(r)&&Number.isFinite(a))return`${this._formatMaintenanceHours(r)} left of ${this._formatMaintenanceHours(a)}`;let n=Number(e?.used_since_reset_hours??e?.current_usage_hours);return Number.isFinite(n)?`${this._formatMaintenanceHours(n)} used since reset`:""},i._formatMaintenanceHours=function(e){let t=Number(e);if(!Number.isFinite(t))return"0 hours";let r=t.toFixed(1).replace(/\.0$/,""),n=Number(r)===1?"hour":"hours";return`${r} ${n}`},i._formatMaintenanceFrequency=function(e){let t=String(e??"").trim();return t?t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):""},i._formatMaintenanceKind=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())},i._formatMaintenanceStatus=function(e){let t=String(e??"").trim().toLowerCase();return t==="replace_now"?"Replace Now":t==="replace_soon"?"Replace Soon":t==="warning"?"Warning":t==="good"?"Good":t==="unknown"?"Unknown":this._formatMaintenanceKind(t||"unknown")},i._formatMaintenanceTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")}}function Tr(i){i.renderRoomAccessModal=function(e){let{state:t}=e;if(!t.isRoomAccessOpen?.())return"";let r=t.activeAccessRoom?.();if(!r)return"";let a=t.accessEditableRooms?.()??[],n=t.accessInboundRooms?.()??[],c=new Set(t.roomAccessFields?.().grants_access_to??[]),s=t.roomAccessValidation?.()??{valid:!0,issues:[]},o=t.roomAccessSaveError?.(),l=t.roomAccessFields?.().is_dock_room??!1;return`
      <div class="evcc-modal-backdrop" data-action="close-room-access">
        <div class="evcc-modal evcc-room-access-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.escapeHtml(r.name)} Access</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-room-access"
              title="Close"
            >\u2715</button>
          </div>

          <div class="evcc-modal-body">

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Dock Room</div>
              <div class="evcc-room-access-help">
                The dock room is the origin of the access tree. It has no inbound dependencies.
                Only one room can be the dock room.
              </div>
              <div class="evcc-chips">
                <button
                  type="button"
                  class="evcc-chip ${l?"active":""}"
                  data-action="toggle-is-dock-room"
                >${l?"This is the Dock Room":"Set as Dock Room"}</button>
              </div>
            </div>

            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Rooms Accessed From Here</div>
              <div class="evcc-room-access-help">
                Select the rooms this room unlocks. A room already claimed by another room
                cannot be selected here.
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${a.length?a.map(d=>{let u=c.has(d.id),v=d.available!==!1,m=d.claimedBy??null,p=m?`Already claimed by Room ${m}`:"";return`
                        <button
                          type="button"
                          class="evcc-chip evcc-room-access-chip
                            ${u?"active":""}
                            ${d.missing?"evcc-room-access-chip--missing":""}
                            ${v?"":"evcc-room-access-chip--claimed"}"
                          data-action="toggle-room-access-target"
                          data-room-id="${this.escapeHtml(d.id)}"
                          ${v?"":"disabled"}
                          ${p?`title="${this.escapeHtml(p)}"`:""}
                        >${this.escapeHtml(d.name)}</button>
                      `}).join(""):'<span class="evcc-room-access-empty">No other rooms are available on this map.</span>'}
              </div>
            </div>

            ${l?"":`
            <div class="evcc-room-access-section">
              <div class="evcc-field-label">Accessed From</div>
              <div class="evcc-room-access-help">
                The room that grants access to this room. Read-only \u2014 set from the other room's editor.
              </div>

              <div class="evcc-chips evcc-room-access-chip-grid">
                ${n.length?n.map(d=>`
                      <span
                        class="evcc-chip evcc-room-access-chip evcc-room-access-chip--readonly ${d.missing?"evcc-room-access-chip--missing":""}"
                      >${this.escapeHtml(d.name)}</span>
                    `).join(""):'<span class="evcc-room-access-empty">No room grants access here yet.</span>'}
              </div>
            </div>
            `}

            ${s.issues?.length?`
              <div class="evcc-room-access-issues">
                <div class="evcc-field-label">Graph Issues</div>
                <div class="evcc-room-access-issue-list">
                  ${s.issues.map(d=>`
                    <div class="evcc-room-access-issue">${this.escapeHtml(d.message??"Invalid room access graph.")}</div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${o?`
              <div class="evcc-room-access-save-error">
                ${this.escapeHtml(o)}
              </div>
            `:""}

          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-access"
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-access"
              ${s.valid?"":"disabled"}
            >Save Access</button>
          </div>

        </div>
      </div>
    `}}function $r(i){i.renderRoomEstimateModal=function(e){let{state:t}=e;if(!t.isRoomEstimateModalOpen?.())return"";let r=t.activeRoomEstimateDetails?.(),a=r?.room??null;if(!a)return"";let n=r.entry??null,c=r.roomEstimate??null,s=r.plannedWaterRoom??null,o=this.card?._learningController?.getRoomProgressSnapshot?.(a.id)??null,l=Number(n?.minutes??c?.minutes),d=n?.eta_at??c?.eta_at??null,u=Number(c?.sample_count),v=Number(c?.battery),m=Number(s?.estimated_robot_water_used_ml),p=Number.isFinite(m),f=[];c?.intensity_mismatch&&f.push("Estimated from different intensity"),c?.source==="default"&&f.push("No learned data yet"),Number(c?.learning_velocity?.runs_to_high??0)>0&&f.push(`${c.learning_velocity.runs_to_high} runs to reliable`);let h=[Number.isFinite(l)?{label:"Estimated time",value:this._formatLearningMinutes(l)}:null,d?{label:"Done by",value:this._formatLearningWallClock(d)}:null,c?.source?{label:"Source",value:String(c.source)}:null,Number.isFinite(u)?{label:"Samples",value:String(u)}:null,Number.isFinite(v)?{label:"Battery",value:String(v)}:null].filter(Boolean),y=[p?{label:"Projected water",value:`~${Math.round(m)} ml`}:null,s?.clean_mode_label?{label:"Mode",value:String(s.clean_mode_label)}:s?.effective_clean_mode?{label:"Mode",value:String(s.effective_clean_mode)}:null,s?.water_level_label?{label:"Water level",value:String(s.water_level_label)}:s?.effective_water_level?{label:"Water level",value:String(s.effective_water_level)}:null].filter(Boolean),x=o?[{label:"Progress",value:`${Math.max(0,Math.min(100,Number(o.percent??0)))}%`},Number.isFinite(o.elapsedMinutes)?{label:"Elapsed",value:this._formatLearningMinutes(o.elapsedMinutes)}:null,Number.isFinite(o.remainingMinutes)?{label:"Remaining",value:this._formatLearningMinutes(o.remainingMinutes)}:null].filter(Boolean):[],w=[];return Number.isFinite(l)&&w.push(this._formatLearningMinutes(l)),d&&w.push(`done by ${this._formatLearningWallClock(d)}`),`
      <div class="evcc-modal-backdrop" data-action="close-room-estimate">
        <div class="evcc-modal evcc-room-estimate-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title-group">
              <div class="evcc-modal-title">${this.escapeHtml(a.name)} Estimate</div>
              ${w.length?`
                <div class="evcc-room-estimate-subtitle">${this.escapeHtml(w.join(" - "))}</div>
              `:""}
            </div>

            <div class="evcc-room-estimate-header-actions">
              ${typeof this.renderConfidenceChip=="function"&&r.confidenceBreakpoint?this.renderConfidenceChip(r.confidenceBreakpoint,this._learningConfidenceLabel(r.confidenceLabel,"room")):""}
              <button
                type="button"
                class="evcc-chip evcc-chip--icon"
                data-action="close-room-estimate"
                title="Close"
              >X</button>
            </div>
          </div>

          <div class="evcc-modal-body">
            ${h.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Estimate Summary</div>
                <div class="evcc-room-estimate-grid">
                  ${h.map(g=>`
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(g.label)}</span>
                      <span>${this.escapeHtml(g.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${y.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Water Projection</div>
                <div class="evcc-room-estimate-grid">
                  ${y.map(g=>`
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(g.label)}</span>
                      <span>${this.escapeHtml(g.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${x.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Live Progress</div>
                <div class="evcc-room-estimate-grid">
                  ${x.map(g=>`
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(g.label)}</span>
                      <span>${this.escapeHtml(g.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${f.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Learning Notes</div>
                <div class="evcc-room-estimate-notes">
                  ${f.map(g=>`
                    <div class="evcc-room-estimate-note">${this.escapeHtml(g)}</div>
                  `).join("")}
                </div>
              </div>
            `:`
              <div class="evcc-room-estimate-empty">
                No extra estimate notes for this room right now.
              </div>
            `}
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-estimate"
            >Close</button>
          </div>

        </div>
      </div>
    `}}function Mr(i){i.renderRoomEditorModal=function(e){let{state:t}=e;if(!t.isRoomEditorOpen())return"";let r=t.activeEditorRoom(),a=t.editorFields();if(!r||!a)return"";let n=t.isEditorRoomCarpet();return`
      <div class="evcc-modal-backdrop" data-action="close-room-editor">
        <div class="evcc-modal evcc-room-editor-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${this.escapeHtml(r.name)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-room-editor"
              title="Close"
            >\u2715</button>
          </div>

          ${n?`
            <div class="evcc-room-editor-carpet-notice">
              \u{1FAB5} Carpet room \u2014 locked to vacuum-only modes
            </div>
          `:""}

          <div class="evcc-room-editor-include-row">
            <span class="evcc-room-editor-include-label">Current queue status:</span>
            <button
              type="button"
              class="evcc-chip evcc-chip--toggle-include ${r.enabled?"active":""}"
              data-action="toggle-room"
              data-room-id="${r.id}"
              data-map-id="${this.escapeHtml(r.mapId)}"
              data-enabled="${r.enabled?"true":"false"}"
            >${r.enabled?"Included":"Excluded"}</button>
          </div>

          <div class="evcc-editor-field-groups">

            ${this._renderProfileSelector(t,r,a)}
            ${this._renderCleanModeField(t,a)}
            ${this._renderSuctionField(t,a)}
            ${t.showWaterLevel()?this._renderWaterLevelField(t,a):""}
            ${this._renderIntensityField(t,a)}
            ${this._renderPassesField(a)}
            ${t.showEdgeMopping()?this._renderEdgeMoppingField(a):""}
            ${this._renderTransitionField(r)}

          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="open-room-access"
              data-room-id="${r.id}"
              data-map-id="${this.escapeHtml(r.mapId)}"
            >Access</button>

            <button
              type="button"
              class="evcc-chip"
              data-action="close-room-editor"
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="save-room-editor"
            >Save</button>
          </div>

        </div>
      </div>
    `},i._renderProfileSelector=function(e,t,r){let a=e.isCustomProfile(),n=e.roomProfilesList?.()??[],c=e.currentEditorManagedProfileName?.(),s=c?e.roomProfileDefinition?.(c):null,o=c?e.isProtectedRoomProfile?.(c):!1,l=(e.customRoomProfiles?.()??[]).length>0;return n.length===0?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Profile</div>
        <div class="evcc-chips">

          <button
            type="button"
            class="evcc-chip evcc-chip--custom ${a?"active":""}"
            data-field="profile_name"
            data-value="custom"
            ${a?"disabled":""}
          >Custom</button>

          ${n.map(d=>`
            <button
              type="button"
              class="evcc-chip ${!a&&r.profile_name===d.name?"active":""}"
              data-field="profile_name"
              data-value="${this.escapeHtml(d.name)}"
              data-action="apply-profile"
            >${this.escapeHtml(d.label)}</button>
          `).join("")}

        </div>

        <div class="evcc-room-profile-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="save-room-profile-as-new"
          >Save as New</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="overwrite-room-profile"
            ${l?"":"disabled"}
          >Save Over</button>

          <button
            type="button"
            class="evcc-chip"
            data-action="rename-room-profile"
            ${c&&s&&!o?"":"disabled"}
          >Rename</button>

          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-room-profile"
            ${c&&s&&!o?"":"disabled"}
          >Delete</button>
        </div>

        <div class="evcc-room-profile-meta">
          ${a?"Current room settings are custom and not linked to a saved profile.":s?`${this.escapeHtml(s.label)} is ${o?"built in and read-only":"a custom reusable profile"}.`:"Select a profile to apply reusable room settings."}
        </div>
      </div>
    `},i._renderCleanModeField=function(e,t){let r=e.cleanModeOptions();return r.length===0?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Mode</div>
        <div class="evcc-chips">
          ${r.map(a=>`
            <button
              type="button"
              class="evcc-chip ${t.clean_mode===a?"active":""}"
              data-field="clean_mode"
              data-value="${this.escapeHtml(a)}"
            >${this.escapeHtml(a)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderSuctionField=function(e,t){let r=e.suctionLevelOptions();return r.length===0?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Suction Level</div>
        <div class="evcc-chips">
          ${r.map(a=>`
            <button
              type="button"
              class="evcc-chip ${t.fan_speed===a?"active":""}"
              data-field="fan_speed"
              data-value="${this.escapeHtml(a)}"
            >${this.escapeHtml(a)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderWaterLevelField=function(e,t){let r=e.waterLevelOptions();return r.length===0?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Water Level</div>
        <div class="evcc-chips">
          ${r.map(a=>`
            <button
              type="button"
              class="evcc-chip ${t.water_level===a?"active":""}"
              data-field="water_level"
              data-value="${this.escapeHtml(a)}"
            >${this.escapeHtml(a)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderIntensityField=function(e,t){let r=e.cleanIntensityOptions();return r.length===0?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Path</div>
        <div class="evcc-chips">
          ${r.map(a=>`
            <button
              type="button"
              class="evcc-chip ${t.clean_intensity===a?"active":""}"
              data-field="clean_intensity"
              data-value="${this.escapeHtml(a)}"
            >${this.escapeHtml(a)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderPassesField=function(e){return`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Passes</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${e.clean_passes===1?"active":""}"
            data-field="clean_passes"
            data-value="1"
          >1 Pass</button>
          <button
            type="button"
            class="evcc-chip ${e.clean_passes===2?"active":""}"
            data-field="clean_passes"
            data-value="2"
          >2 Passes</button>
        </div>
      </div>
    `},i._renderTransitionField=function(e){let t=!!(e.isTransition??e.is_transition);return`
      <div class="evcc-editor-field-group evcc-editor-field-group--transition">
        <div class="evcc-field-label">Transition Space</div>
        ${!!(e.transitionCandidate??e.transition_candidate)&&!t?`<div class="evcc-room-editor-transition-callout">
           Shape analysis suggests this may be a hallway or connecting corridor.
         </div>`:""}
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${t?"active":""}"
            data-action="toggle-room-transition"
            data-room-id="${this.escapeHtml(String(e.id))}"
            data-map-id="${this.escapeHtml(String(e.mapId))}"
            data-value="${t?"false":"true"}"
          >${t?"Transition Space":"Mark as Transition"}</button>
        </div>
      </div>
    `},i._renderEdgeMoppingField=function(e){return`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Edge Mopping</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${e.edge_mopping?"active":""}"
            data-field="edge_mopping"
            data-value="true"
          >On</button>
          <button
            type="button"
            class="evcc-chip ${e.edge_mopping?"":"active"}"
            data-field="edge_mopping"
            data-value="false"
          >Off</button>
        </div>
      </div>
    `}}var di=new Set(["is_on","is_off","exists","missing"]),ui=[{value:"vacuum",label:"Vacuum"},{value:"mop",label:"Mop"},{value:"vacuum_mop",label:"Vacuum & Mop"}],mi=[{value:"Quiet",label:"Quiet"},{value:"Standard",label:"Standard"},{value:"Boost",label:"Boost"},{value:"Max",label:"Max"}],vi=[{value:"Off",label:"Off"},{value:"Low",label:"Low"},{value:"Medium",label:"Medium"},{value:"High",label:"High"}],pi=[{value:"Quick",label:"Quick"},{value:"Narrow",label:"Narrow"},{value:"Deep",label:"Deep"}];function Ir(i){i.renderRoomRulesView=function(e){let{state:t}=e,r=t.getRoomsForActiveMap?.()??[];if(!r.length)return`
        <div class="evcc-room-rules-view">
          <div class="evcc-empty">No rooms found. Run the discover rooms service to get started.</div>
        </div>
      `;let a=t.resolvedRoomRulesRoom?.(),n=t.roomRulesDraft?.(),c=t.roomRulesDraftMode?.(),s=t.roomRulesSaveError?.();return`
      <div class="evcc-room-rules-view">
        ${this._renderRoomRulesSubtabs(r,a)}
        <div class="evcc-room-rules-content">
          ${a?n?this._renderRuleEditor(t,a,n,c,s):this._renderRuleList(t,a):'<div class="evcc-empty">Select a room above.</div>'}
        </div>
      </div>
    `},i._renderRoomRulesSubtabs=function(e,t){return`
      <div class="evcc-room-rules-subtabs">
        ${[...e].sort((a,n)=>(a.order??0)-(n.order??0)).map(a=>{let n=t&&String(a.id)===String(t.id),c=Array.isArray(a.rules)?a.rules.length:0;return`
            <button
              type="button"
              class="evcc-room-rules-subtab ${n?"active":""}"
              data-action="set-room-rules-tab"
              data-room-id="${this.escapeHtml(String(a.id))}"
            >
              ${this.escapeHtml(a.name)}
              ${c?`<span class="evcc-room-rules-subtab-count">${c}</span>`:""}
            </button>
          `}).join("")}
      </div>
    `},i._renderRuleList=function(e,t){let r=e.roomRulesForRoom?.(t.id)??[];return`
      <div class="evcc-rule-list">
        ${r.length?r.map(a=>this._renderRuleCard(e,a)).join(""):`<div class="evcc-rule-list-empty">No rules configured for ${this.escapeHtml(t.name)}.</div>`}

        <div class="evcc-rule-list-actions">
          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="open-new-rule"
          >+ Add Rule</button>
        </div>
      </div>
    `},i._renderRuleCard=function(e,t){let r=e.ruleConditionSummary?.(t)??"",a=e.ruleEffectSummary?.(t)??"",n=t.label||t.entity_id||"Unnamed rule",c=t.kind==="blocker";return`
      <div class="evcc-rule-card ${t.enabled?"":"evcc-rule-card--disabled"}">
        <div class="evcc-rule-card-body">
          <span class="evcc-rule-kind-badge evcc-rule-kind-badge--${c?"blocker":"modifier"}">
            ${c?"Blocker":"Modifier"}
          </span>

          <div class="evcc-rule-info">
            <div class="evcc-rule-label">${this.escapeHtml(n)}</div>
            ${t.label?`<div class="evcc-rule-entity">${this.escapeHtml(t.entity_id)}</div>`:""}
            <div class="evcc-rule-condition">${this.escapeHtml(r)}</div>
            <div class="evcc-rule-effect">${this.escapeHtml(a)}</div>
          </div>

          ${t.enabled?"":'<span class="evcc-rule-disabled-tag">Disabled</span>'}
        </div>

        <div class="evcc-rule-card-actions">
          <button
            type="button"
            class="evcc-chip"
            data-action="edit-rule"
            data-rule-id="${this.escapeHtml(String(t.id??""))}"
          >Edit</button>
          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-rule"
            data-rule-id="${this.escapeHtml(String(t.id??""))}"
          >Delete</button>
        </div>
      </div>
    `},i._renderRuleEditor=function(e,t,r,a,n){let c=a==="new",s=r.kind==="modifier",o=e.ruleEntityDescriptor?.(r)??null,l=e.ruleOperatorGroups?.(r)??[],d=e.ruleEntitySearchResults?.(r.entity_id,10)??[],u=di.has(r.operator??""),v=e.roomRulesDraftIsValid?.()??!1;return`
      <div class="evcc-rule-editor">
        <div class="evcc-rule-editor-header">
          <div class="evcc-rule-editor-title">
            ${c?"New Rule":"Edit Rule"} - ${this.escapeHtml(t.name)}
          </div>
        </div>

        <div class="evcc-rule-editor-body">
          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">Rule Type</div>
            <div class="evcc-chips">
              <button
                type="button"
                class="evcc-chip ${r.kind==="blocker"?"active":""}"
                data-rule-field="kind"
                data-rule-value="blocker"
              >Blocker</button>
              <button
                type="button"
                class="evcc-chip ${r.kind==="modifier"?"active":""}"
                data-rule-field="kind"
                data-rule-value="modifier"
              >Modifier</button>
            </div>
            <div class="evcc-rule-editor-help">
              ${r.kind==="blocker"?"Skip this room entirely when the condition is true.":"Override this room's cleaning settings when the condition is true."}
            </div>
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-label">Label <span class="evcc-rule-editor-optional">(optional)</span></label>
            <input
              id="rule-label"
              type="text"
              class="evcc-rule-editor-input"
              placeholder="e.g. Skip when door is open"
              value="${this.escapeHtml(r.label??"")}"
              data-rule-input="label"
            />
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-entity">Entity ID</label>
            <input
              id="rule-entity"
              type="text"
              class="evcc-rule-editor-input ${o?.entityExists?"":"evcc-rule-editor-input--error"}"
              placeholder="binary_sensor.front_door"
              value="${this.escapeHtml(r.entity_id??"")}"
              data-rule-input="entity_id"
            />
            ${this._renderRuleEntitySearchResults(r,d)}
            ${this._renderRuleEntityHelp(o)}
          </div>

          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">Condition</div>
            ${l.map(m=>`
              <div class="evcc-rule-operator-group">
                <div class="evcc-rule-operator-group-label">${this.escapeHtml(m.label)}</div>
                <div class="evcc-chips">
                  ${m.operators.map(p=>`
                    <button
                      type="button"
                      class="evcc-chip ${r.operator===p.value?"active":""}"
                      data-rule-field="operator"
                      data-rule-value="${this.escapeHtml(p.value)}"
                    >${this.escapeHtml(p.label)}</button>
                  `).join("")}
                </div>
              </div>
            `).join("")}
          </div>

          ${u?"":this._renderRuleValueField(e,r,o)}

          <div class="evcc-rule-editor-section">
            <div class="evcc-field-label">Enabled</div>
            <div class="evcc-chips">
              <button
                type="button"
                class="evcc-chip ${r.enabled?"active":""}"
                data-rule-field="enabled"
                data-rule-value="true"
              >Yes</button>
              <button
                type="button"
                class="evcc-chip ${r.enabled?"":"active"}"
                data-rule-field="enabled"
                data-rule-value="false"
              >No</button>
            </div>
          </div>

          <div class="evcc-rule-editor-section">
            <label class="evcc-field-label" for="rule-reason">
              Reason <span class="evcc-rule-editor-optional">(optional)</span>
            </label>
            <input
              id="rule-reason"
              type="text"
              class="evcc-rule-editor-input"
              placeholder="${s?"e.g. Reduce water near door":"e.g. Door open"}"
              value="${this.escapeHtml(r.effect?.reason??"")}"
              data-rule-input="effect.reason"
            />
          </div>

          ${s?this._renderModifierChanges(r):""}
        </div>

        ${n?`<div class="evcc-rule-editor-save-error">${this.escapeHtml(n)}</div>`:""}

        <div class="evcc-rule-editor-footer">
          <button
            type="button"
            class="evcc-chip"
            data-action="cancel-rule-editor"
          >Cancel</button>
          <button
            type="button"
            class="evcc-chip evcc-chip--save"
            data-action="save-rule"
            ${v?"":"disabled"}
          >${c?"Add Rule":"Save Rule"}</button>
        </div>
      </div>
    `},i._renderRuleEntityHelp=function(e){if(!e?.entityId)return'<div class="evcc-rule-editor-help">Choose a Home Assistant entity to drive this rule.</div>';if(!e.entityExists)return'<div class="evcc-rule-editor-help">This entity is not currently available in Home Assistant.</div>';let t=[`${this.escapeHtml(e.entityLabel)}`,`Type: ${this.escapeHtml(e.category)}`];return e.currentState!=null&&t.push(`Current: ${this.escapeHtml(String(e.currentState))}`),e.unit&&t.push(`Unit: ${this.escapeHtml(String(e.unit))}`),e.category==="enum"&&e.options?.length&&t.push(`${e.options.length} option${e.options.length===1?"":"s"}`),`<div class="evcc-rule-editor-help">${t.join(" \u2022 ")}</div>`},i._renderRuleEntitySearchResults=function(e,t){return String(e?.entity_id??"").trim().length<2?"":t.length?`
      <div class="evcc-rule-entity-search">
        ${t.map(a=>`
          <button
            type="button"
            class="evcc-rule-entity-search-result ${String(e?.entity_id??"")===String(a.entity_id)?"active":""}"
            data-rule-entity-select="${this.escapeHtml(String(a.entity_id))}"
          >
            <span class="evcc-rule-entity-search-title">${this.escapeHtml(a.friendly_name||a.entity_id)}</span>
            <span class="evcc-rule-entity-search-meta">
              ${this.escapeHtml(a.entity_id)}
              ${a.state!=null?` \u2022 ${this.escapeHtml(String(a.state))}`:""}
            </span>
          </button>
        `).join("")}
      </div>
    `:'<div class="evcc-rule-entity-search-empty">No matching Home Assistant entities found.</div>'},i._renderRuleValueField=function(e,t,r){let a=r?.valueModeForOperator?.(t.operator)??"text",n=t.value;if(a==="single-select"&&r?.options?.length)return`
        <div class="evcc-rule-editor-section">
          <label class="evcc-field-label" for="rule-value-select">Value</label>
          <select
            id="rule-value-select"
            class="evcc-rule-editor-input"
            data-rule-select="value"
          >
            <option value="">Select a value</option>
            ${r.options.map(c=>`
              <option
                value="${this.escapeHtml(String(c.value))}"
                ${String(n??"")===String(c.value)?"selected":""}
              >${this.escapeHtml(c.label)}</option>
            `).join("")}
          </select>
        </div>
      `;if(a==="multi-select"&&r?.options?.length){let c=Array.isArray(n)?n.map(String):[];return`
        <div class="evcc-rule-editor-section">
          <div class="evcc-field-label">Value</div>
          <div class="evcc-chips">
            ${r.options.map(s=>`
              <button
                type="button"
                class="evcc-chip ${c.includes(String(s.value))?"active":""}"
                data-rule-multivalue="${this.escapeHtml(String(s.value))}"
              >${this.escapeHtml(s.label)}</button>
            `).join("")}
          </div>
          <div class="evcc-rule-editor-help">Choose one or more allowed values from the entity itself.</div>
        </div>
      `}return a==="number"?`
        <div class="evcc-rule-editor-section">
          <label class="evcc-field-label" for="rule-value-number">Value</label>
          <input
            id="rule-value-number"
            type="number"
            class="evcc-rule-editor-input"
            value="${this.escapeHtml(n==null?"":String(n))}"
            ${r?.min!=null?`min="${r.min}"`:""}
            ${r?.max!=null?`max="${r.max}"`:""}
            ${r?.step!=null?`step="${r.step}"`:""}
            data-rule-number-input="value"
          />
          ${r?.unit||r?.min!=null||r?.max!=null?`<div class="evcc-rule-editor-help">${[r?.unit?`Unit: ${this.escapeHtml(String(r.unit))}`:null,r?.min!=null?`Min: ${r.min}`:null,r?.max!=null?`Max: ${r.max}`:null].filter(Boolean).join(" \u2022 ")}</div>`:""}
        </div>
      `:`
      <div class="evcc-rule-editor-section">
        <label class="evcc-field-label" for="rule-value">Value</label>
        <input
          id="rule-value"
          type="text"
          class="evcc-rule-editor-input"
          placeholder="${t.operator==="in"||t.operator==="not_in"?"value1, value2, ...":"e.g. home, 25, true"}"
          value="${this.escapeHtml(Array.isArray(n)?n.join(", "):String(n??""))}"
          data-rule-input="value"
        />
        ${t.operator==="in"||t.operator==="not_in"?'<div class="evcc-rule-editor-help">Comma-separated list of values.</div>':""}
      </div>
    `},i._renderModifierChanges=function(e){let t=e.effect?.changes??{},r=(a,n,c)=>`
      <div class="evcc-rule-change-row">
        <div class="evcc-rule-change-label">${this.escapeHtml(a)}</div>
        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip evcc-chip--muted ${t[n]==null?"active":""}"
            data-rule-field="effect.changes.${this.escapeHtml(n)}"
            data-rule-value=""
          >-</button>
          ${c.map(s=>`
            <button
              type="button"
              class="evcc-chip ${t[n]===s.value?"active":""}"
              data-rule-field="effect.changes.${this.escapeHtml(n)}"
              data-rule-value="${this.escapeHtml(String(s.value))}"
            >${this.escapeHtml(s.label)}</button>
          `).join("")}
        </div>
      </div>
    `;return`
      <div class="evcc-rule-editor-section">
        <div class="evcc-field-label">Setting Overrides</div>
        <div class="evcc-rule-editor-help">
          Select overrides to apply. "-" means keep the room's saved setting.
        </div>

        ${r("Clean Mode","clean_mode",ui)}
        ${r("Fan Speed","fan_speed",mi)}
        ${r("Water Level","water_level",vi)}
        ${r("Clean Intensity","clean_intensity",pi)}

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">Clean Passes</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${t.clean_passes==null?"active":""}"
              data-rule-field="effect.changes.clean_passes"
              data-rule-value=""
            >-</button>
            ${[1,2].map(a=>`
              <button
                type="button"
                class="evcc-chip ${t.clean_passes===a?"active":""}"
                data-rule-field="effect.changes.clean_passes"
                data-rule-value="${a}"
              >${a}</button>
            `).join("")}
          </div>
        </div>

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">Edge Mopping</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${t.edge_mopping==null?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value=""
            >-</button>
            <button
              type="button"
              class="evcc-chip ${t.edge_mopping===!0?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="true"
            >On</button>
            <button
              type="button"
              class="evcc-chip ${t.edge_mopping===!1?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="false"
            >Off</button>
          </div>
        </div>
      </div>
    `}}function Ar(i){i.renderOrderSelectorModal=function(e){let{state:t}=e;if(!t.isOrderSelectorOpen())return"";let r=t.orderSelectorScope(),a=t.orderSelectorItem(),n=t.orderSelectorTargetPosition(),c=t.orderSelectorPositions(),s=t.getOrderAdapter(r);if(!a||!s)return"";let o=s.getLabel(a);return`
      <div class="evcc-modal-backdrop" data-action="close-order-selector">
        <div class="evcc-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">Move ${this.escapeHtml(o)}</div>
            <button
              type="button"
              class="evcc-chip evcc-chip--icon"
              data-action="close-order-selector"
              title="Close"
            >\u2715</button>
          </div>

          <div class="evcc-modal-body">
            <div class="evcc-editor-field-group">
              <div class="evcc-field-label">Position</div>
              <div class="evcc-chips">
                ${c.map(l=>`
                  <button
                    type="button"
                    class="evcc-chip ${Number(n)===Number(l)?"active":""}"
                    data-action="set-order-position"
                    data-position="${l}"
                  >${l}</button>
                `).join("")}
              </div>
            </div>
          </div>

          <div class="evcc-modal-footer">
            <button
              type="button"
              class="evcc-chip"
              data-action="close-order-selector"
            >Cancel</button>

            <button
              type="button"
              class="evcc-chip evcc-chip--save"
              data-action="confirm-order-selector"
            >Save</button>
          </div>

        </div>
      </div>
    `}}function Cr(i){if(!i)return null;let e=String(i).trim();if(!/^color-mix\(/i.test(e))return null;let t=e.indexOf("("),r=e.lastIndexOf(")");if(t===-1||r===-1)return null;let c=e.slice(t+1,r).replace(/^\s*in\s+\w+\s*,\s*/i,"").match(/^(.*?\s+\d+(?:\.\d+)?%)\s*,\s*(.*?\s+\d+(?:\.\d+)?%)\s*$/);if(!c)return null;let s=/^(.*?)\s+(\d+(?:\.\d+)?)%$/,o=c[1].trim().match(s),l=c[2].trim().match(s);return!o||!l?null:{color1:o[1].trim(),ratio:parseFloat(o[2]),color2:l[1].trim(),ratio2:parseFloat(l[2])}}function hi(i,e,t){let r=Math.max(0,Math.min(100,Math.round(e)));return`color-mix(in srgb, ${i} ${r}%, ${t} ${100-r}%)`}var Ae=new Set(["--evcc-accent","--evcc-surface-base","--evcc-text-primary","--evcc-radius-card"]),fi={"Shared Foundations":{min:0,max:64,step:2},"Cards & Surfaces":{min:0,max:32,step:1},"Borders & Shadows":{min:0,max:32,step:1},Chips:{min:20,max:48,step:1},"Room Cards":{min:0,max:32,step:1},"Floor Textures":{min:0,max:1,step:.01},"Floor Textures \u2014 Tile":{min:0,max:1,step:.01},"Floor Textures \u2014 Wood":{min:0,max:1,step:.01},"Floor Textures \u2014 Marble":{min:0,max:1,step:.01},"Floor Textures \u2014 Concrete":{min:0,max:1,step:.01},"Floor Textures \u2014 Carpet Low":{min:0,max:1,step:.01},"Floor Textures \u2014 Carpet High":{min:0,max:1,step:.01},"Floor Textures \u2014 Granite":{min:0,max:1,step:.01},"Queue & Ordering":{min:0,max:32,step:1},"Status, Confidence & Alerts":{min:0,max:32,step:1},"Learning & Metrics":{min:0,max:32,step:1},"Modals & Overlays":{min:0,max:32,step:1}};function gi(i){let e=parseFloat(String(i||"").trim());return Number.isNaN(e)?null:e}function Lr(i,e){let t=String(e||"").trim();if(!t)return{numeric:null,unit:Ce(i)};if(i.type==="number")return{numeric:gi(t),unit:""};if(i.type==="size"){let r=t.match(/^(-?\d*\.?\d+)\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);return r?{numeric:Number(r[1]),unit:r[2].toLowerCase()}:{numeric:null,unit:Ce(i)}}if(i.type==="duration"){let r=t.match(/^(-?\d*\.?\d+)\s*(ms|s)$/i);return r?{numeric:Number(r[1]),unit:r[2].toLowerCase()}:{numeric:null,unit:Ce(i)}}return{numeric:null,unit:""}}function Ce(i){return i.type==="size"?"px":i.type==="duration"?"ms":""}function _i(i){return i.type==="size"||i.type==="number"||i.type==="duration"}function bi(i,e){return _i(i)?e==null||e===""?!0:Lr(i,e).numeric!==null:!1}function yi(i){let e=Number(i);return Number.isNaN(e)?100:Math.max(0,Math.min(100,e))}function xi(i){let e=String(i||"").trim();if(/^#[0-9a-fA-F]{8}$/.test(e)){let t=e.slice(7,9),r=parseInt(t,16)/255;return yi(Math.round(r*100))}return 100}function Pr(i){i.renderThemeView=function(){let e=this.card._state._ensureThemeState(),{tokens:t,sources:r}=this.card._state.resolvedTheme(),a=e.activeSubTab||"presets";return`
      <div class="evcc-view evcc-view--theme">
        ${this._renderThemeHeader(e)}

        <div class="evcc-chips evcc-theme-tabs" role="tablist">
          <button
            class="evcc-chip ${a==="presets"?"active":""}"
            data-theme-tab="presets"
          >
            Themes
          </button>

          <button
            class="evcc-chip ${a==="palette"?"active":""}"
            data-theme-tab="palette"
          >
            Palette
          </button>

          <button
            class="evcc-chip ${a==="tokens"?"active":""}"
            data-theme-tab="tokens"
          >
            Tokens
          </button>
        </div>

        <div class="evcc-view-content">
          ${a==="presets"?this._renderThemePresets(e):""}
          ${a==="palette"?this._renderThemePalette(t,r):""}
          ${a==="tokens"?this._renderThemeTokenEditor(t,r):""}
        </div>

        ${this._renderThemeFooter(e)}
      </div>
    `},i._renderThemeHeader=function(e){return`
      <div class="evcc-theme-header">
        <div class="evcc-search-box">
          <ha-icon icon="mdi:magnify"></ha-icon>
          <input
            type="text"
            placeholder="Search tokens..."
            value="${this.escapeHtml(e.tokenSearchQuery||"")}"
            data-theme-search
          />
        </div>

        <label class="evcc-modified-toggle">
          <ha-checkbox
            ?checked="${e.modifiedOnly}"
            data-theme-modified-only
          ></ha-checkbox>
          <span>Modified Only</span>
        </label>
      </div>
    `},i._renderThemeGroupFilters=function(){let e=this.card._state.getThemeGroupFilter();return`
      <div class="evcc-chips evcc-theme-filters">
        ${[{value:"all",label:"All"},{value:"modified",label:"Modified"},...K.map(r=>({value:r,label:r}))].map(r=>`
          <button
            class="evcc-chip ${e===r.value?"active":""}"
            data-theme-group-filter="${this.escapeHtml(r.value)}"
          >
            ${this.escapeHtml(r.label)}
          </button>
        `).join("")}
      </div>
    `},i._renderThemePresets=function(e){let t=e.library||{},r=Object.keys(t);return r.length===0?'<div class="evcc-empty">No themes available.</div>':`
      <div class="evcc-preset-grid">
        ${r.map(a=>{let n=t[a],c=e.activeThemeId===a,s=[...Object.entries(n.tokens||{}),...Object.entries(n.colors||{}),...Object.entries(n.alpha||{})].map(([o,l])=>`${o}:${l}`).join(";");return`
            <div
              class="evcc-preset-card ${c?"active":""}"
              data-theme-preset="${this.escapeHtml(a)}"
            >
              ${a!==e.defaultThemeId?`
                <button
                  class="evcc-preset-delete"
                  data-action="delete-preset"
                  data-preset-id="${this.escapeHtml(a)}"
                >
                  <ha-icon icon="mdi:close-circle"></ha-icon>
                </button>
              `:""}

              <div class="evcc-preset-preview" style="${s}">
                <div class="preview-swatch accent"></div>
                <div class="preview-swatch surface"></div>
              </div>

              <div class="evcc-preset-label">
                ${this.escapeHtml(n.name||a)}
                ${c?'<span class="evcc-chip evcc-chip--active">Active</span>':""}
              </div>
            </div>
          `}).join("")}
      </div>
    `},i._renderThemePalette=function(e,t){let r=re.filter(a=>Ae.has(a.key));return`
      <div class="evcc-theme-editor-pane">
        ${this._renderThemePreviewPane()}

        <div class="evcc-theme-editor-main evcc-theme-editor-main--palette">
          <div class="evcc-theme-editor-scrollbox">
          <div class="evcc-token-list evcc-token-list--palette">
          ${r.map(a=>this._renderThemeTokenRow(a,e[a.key],t[a.key])).join("")}
          </div>
          </div>
        </div>
      </div>
    `},i._renderThemeTokenEditor=function(e,t){let r=this.card._state.getThemeGroupFilter(),a={},n=new Set;for(let o of K){let l=o.indexOf(" \u2014 ");if(l===-1)continue;let d=o.slice(0,l);K.includes(d)&&((a[d]=a[d]??[]).push(o),n.add(o))}let c=(o,l=!1)=>{let d=this.card._state.filteredThemeTokensForGroup(o,re,{excludeKeys:Ae}),u=this.card._state.getThemeGroupSearchQuery(o),v=String(u||"").trim().length>0,m=r===o||v,f=(a[o]??[]).map(g=>c(g,!0)).filter(Boolean).join("");if(!d.length&&!m&&!f)return"";let h=this.card._state.themeGroupCounts(o,re,{excludeKeys:Ae}),x=this.card._state.shouldForceThemeGroupOpenForSearch(o,re,{excludeKeys:Ae})||this.card._state.isThemeGroupOpen(o),w=l?o.slice(o.lastIndexOf(" \u2014 ")+3):o;return`
        <div
          class="evcc-token-group ${x?"is-open":"is-closed"} ${l?"evcc-token-group--child":""}"
          data-theme-group-name="${this.escapeHtml(o)}"
        >
          <div
            class="evcc-token-group-header"
            data-theme-group-toggle="${this.escapeHtml(o)}"
          >
            <div class="group-title">
              ${this.escapeHtml(w)} (${h.modified} / ${h.total})
            </div>

            <div class="group-actions">
              ${h.modified>0?`
                <button
                  class="evcc-chip"
                  data-theme-group-reset="${this.escapeHtml(o)}"
                >
                  Reset
                </button>
              `:""}

              <span class="group-toggle">
                ${x?"\xE2\u2013\xBE":"\xE2\u2013\xB8"}
              </span>
            </div>
          </div>

          ${x?`
            <div class="evcc-token-group-body">
              ${d.length?`
                <div class="evcc-token-group-search">
                  <input
                    type="text"
                    placeholder="Search ${this.escapeHtml(w)}..."
                    value="${this.escapeHtml(u)}"
                    data-theme-group-search="${this.escapeHtml(o)}"
                  />
                </div>

                ${d.map(g=>this._renderThemeTokenRow(g,e[g.key],t[g.key])).join("")}

                ${!d.length&&v?`
                  <div class="evcc-empty evcc-empty--theme-group-search">
                    No tokens in ${this.escapeHtml(w)} match "${this.escapeHtml(u)}".
                  </div>
                `:""}
              `:""}

              ${f}
            </div>
          `:""}
        </div>
      `},s=K.filter(o=>!n.has(o)).map(o=>c(o)).filter(Boolean);return`
      <div class="evcc-theme-editor-pane">
        ${this._renderThemePreviewPane()}

        <div class="evcc-theme-editor-main">
        <div class="evcc-theme-editor-scrollbox">
        <div class="evcc-token-editor">
          ${this._renderThemeGroupFilters()}

          <div class="evcc-token-list">
          ${s.length?s.join(""):`
            <div class="evcc-empty evcc-empty--theme-group-search">
              No tokens match the current theme filters.
            </div>
          `}
          </div>
        </div>
        </div>
        </div>
      </div>
    `},i._renderThemeTokenRow=function(e,t,r){let a=r==="draft",n=t||"";return e.type==="color"?Cr(n)?this._renderThemeColorMixTokenRow(e,n,a):this._renderThemeColorTokenRow(e,n,a):bi(e,n)?this._renderThemeNumericTokenRow(e,n,a):this._renderThemeTextTokenRow(e,n,a)},i._renderThemeColorTokenRow=function(e,t,r){let a=String(t||"").trim(),n=this._safeColorInputValue(a),c=xi(a),s=/^#[0-9a-fA-F]{8}$/.test(a)?`#${a.slice(1,7)}`:a;return`
      <div class="evcc-token-row evcc-token-row--color ${r?"is-draft":""}">
        <div class="token-top-strip">
          <input
            type="text"
            class="token-input token-input--hex"
            value="${this.escapeHtml(a)}"
            placeholder="#RRGGBB"
            data-theme-token="${this.escapeHtml(e.key)}"
            inputmode="text"
            autocapitalize="off"
            spellcheck="false"
          />

          ${r?`
            <button
              class="evcc-chip"
              data-theme-reset="${this.escapeHtml(e.key)}"
            >
              Reset
            </button>
          `:""}

          <div class="token-hint">
            Drag for opacity \xB7 Double tap for color
          </div>
        </div>

        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(e.label)}
          </div>
        </div>

        <div class="token-control-row token-control-row--color">
          <div class="token-color-combined-control" title="${this.escapeHtml(e.label)}">
            <div
              class="token-alpha-shell"
              style="
                --rail-color: ${s||`var(${e.key})`};
                --thumb-color: ${a||`var(${e.key})`};
              "
            >
              <div class="token-alpha-rail">
                <div class="token-alpha-rail-fill"></div>
                <div class="token-alpha-rail-track"></div>

                <input
                  type="range"
                  class="token-alpha-input"
                  min="0"
                  max="100"
                  step="1"
                  value="${c}"
                  data-theme-alpha="${this.escapeHtml(e.key)}"
                  data-color-swatch="${this.escapeHtml(e.key)}"
                  aria-label="${this.escapeHtml(e.label)} opacity"
                />

                <div
                  class="token-alpha-indicator"
                  data-theme-alpha-indicator="${this.escapeHtml(e.key)}"
                  style="left: ${c}%"
                ></div>
              </div>

              <div
                class="token-slider-bubble token-slider-bubble--alpha"
                data-theme-alpha-bubble="${this.escapeHtml(e.key)}"
                style="left: ${c}%"
              >
                ${c}%
              </div>
            </div>
          </div>

          <input
            type="color"
            class="hidden-color-input"
            value="${n}"
            data-theme-color-input="${this.escapeHtml(e.key)}"
            tabIndex="-1"
          />
        </div>
      </div>
    `},i._renderThemeColorMixTokenRow=function(e,t,r){let a=Cr(t);if(!a)return this._renderThemeColorTokenRow(e,t,r);let{color1:n,ratio:c,color2:s}=a,o=this.escapeHtml(hi(n,c,s));return`
      <div class="evcc-token-row evcc-token-row--color-mix ${r?"is-draft":""}">
        <div class="token-head">
          <div class="token-label">${this.escapeHtml(e.label)}</div>
          <div class="token-head-actions">
            ${r?`
              <button class="evcc-chip" data-theme-reset="${this.escapeHtml(e.key)}">
                Reset
              </button>
            `:""}
          </div>
        </div>

        <div class="token-hint">Drag ratio \xB7 Edit color references</div>

        <div class="token-colormix-colors">
          <div class="token-colormix-slot">
            <div class="token-colormix-swatch" style="background: ${this.escapeHtml(n)}"></div>
            <input
              type="text"
              class="token-input token-colormix-color"
              data-theme-colormix="${this.escapeHtml(e.key)}"
              data-colormix-part="color1"
              value="${this.escapeHtml(n)}"
              spellcheck="false"
              autocapitalize="off"
            />
          </div>

          <div class="token-colormix-ratio-label" data-colormix-ratio-label="${this.escapeHtml(e.key)}">
            ${c}%
          </div>

          <div class="token-colormix-slot">
            <div class="token-colormix-swatch" style="background: ${this.escapeHtml(s)}"></div>
            <input
              type="text"
              class="token-input token-colormix-color"
              data-theme-colormix="${this.escapeHtml(e.key)}"
              data-colormix-part="color2"
              value="${this.escapeHtml(s)}"
              spellcheck="false"
              autocapitalize="off"
            />
          </div>
        </div>

        <div class="token-colormix-slider-row">
          <input
            type="range"
            class="token-colormix-ratio-input"
            min="0"
            max="100"
            step="1"
            value="${c}"
            data-theme-colormix="${this.escapeHtml(e.key)}"
            data-colormix-part="ratio"
          />
        </div>

        <div
          class="token-colormix-preview"
          style="background: ${o}"
        ></div>
      </div>
    `},i._renderThemeNumericTokenRow=function(e,t,r){let a=fi[e.group]||{min:0,max:64,step:1},n=Lr(e,t),c=n.numeric??a.min,s=n.unit||Ce(e),o=e.type==="number"?"":s,l=Math.min(a.min,c),d=Math.max(a.max,c);return`
      <div
        class="evcc-token-row evcc-token-row--numeric ${r?"is-draft":""}"
        data-theme-token-unit="${this.escapeHtml(s)}"
      >
        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(e.label)}
            <span class="evcc-chip">${this.escapeHtml(e.type)}</span>
          </div>

          <div class="token-head-actions">
            ${r?`
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(e.key)}"
              >
                Reset
              </button>
            `:""}
          </div>
        </div>

        <div class="token-control-row token-control-row--slider">
          <div class="slider-wrap">
            <input
              type="range"
              class="token-input token-input--slider"
              min="${l}"
              max="${d}"
              step="${a.step}"
              value="${c}"
              data-theme-token="${this.escapeHtml(e.key)}"
            />

            <div
              class="token-slider-bubble"
              data-theme-slider-bubble="${this.escapeHtml(e.key)}"
            >
              ${c}${this.escapeHtml(o)}
            </div>
          </div>
        </div>

        <div class="token-control-row token-control-row--number">
          <input
            type="number"
            class="token-input token-input--number"
            min="${l}"
            max="${d}"
            step="${a.step}"
            value="${c}"
            data-theme-token="${this.escapeHtml(e.key)}"
          />
        </div>
      </div>
    `},i._renderThemeTextTokenRow=function(e,t,r){return`
      <div class="evcc-token-row evcc-token-row--text ${r?"is-draft":""}">
        <div class="token-head">
          <div class="token-label">
            ${this.escapeHtml(e.label)}
            <span class="evcc-chip">${this.escapeHtml(e.type)}</span>
            ${r?'<span class="evcc-chip evcc-chip--custom">Draft</span>':""}
          </div>

          <div class="token-head-actions">
            ${r?`
              <button
                class="evcc-chip"
                data-theme-reset="${this.escapeHtml(e.key)}"
              >
                Reset
              </button>
            `:""}
          </div>
        </div>

        <div class="token-control-row token-control-row--text">
          <input
            type="text"
            class="token-input"
            value="${this.escapeHtml(t)}"
            placeholder="Default"
            data-theme-token="${this.escapeHtml(e.key)}"
          />
        </div>
      </div>
    `},i._renderThemeFooter=function(e){let t=!!e.draftDirty,r=!!e.activeThemeId;return`
      <div class="evcc-view-footer">
        <div class="footer-left">
          <button class="evcc-chip" data-action="export-theme">
            Export
          </button>

          <button class="evcc-chip" data-action="import-theme">
            Import
          </button>
        </div>

        <div class="footer-right">
          <button
            class="evcc-chip"
            data-action="reset-draft"
            ${t?"":"disabled"}
          >
            Discard
          </button>

          <button
            class="evcc-chip evcc-chip--save"
            data-action="save-theme"
            ${t?"":"disabled"}
          >
            ${r?"Save Changes":"Save as New"}
          </button>
        </div>
      </div>
    `},i._safeColorInputValue=function(e){let t=String(e||"").trim();return/^#[0-9a-fA-F]{6}$/.test(t)?t:/^#[0-9a-fA-F]{8}$/.test(t)?`#${t.slice(1,7)}`:"#000000"}}var Or=Object.freeze({"App Shell & Typography":{method:"_renderThemePreviewShellTypography",title:"Shell & Typography Preview",description:"Accent, heading, and body text examples show the shell voice this group controls."},"Cards & Surfaces":{method:"_renderThemePreviewCardsSurfaces",title:"Cards & Surfaces Preview",description:"Shared card, panel, and input surfaces show the base material language for the editor."},"Borders & Shadows":{method:"_renderThemePreviewBordersShadows",title:"Borders & Shadows Preview",description:"Border strength and elevation samples reveal separation, depth, and hover lift."},Chips:{method:"_renderThemePreviewChips",title:"Chip Preview",description:"A compact chip matrix highlights default, active, hover, success, warning, and excluded states."},"Room Cards":{method:"_renderThemePreviewRoomCards",title:"Room Card Preview",description:"Mini room cards expose profile chips, room chips, and room-surface treatment together."},"Floor Textures":{method:"_renderThemePreviewFloorTextures",title:"Floor Texture Preview",description:"Live swatches show each material's overlay on the card surface. Opacity, scale, and tint tokens update in real time."},"Floor Textures \u2014 Tile":{method:"_renderThemePreviewFloorTextureTile",title:"Tile Floor Preview",description:"Base and accent colors control the grout lines and tile face on card and map surfaces."},"Floor Textures \u2014 Wood":{method:"_renderThemePreviewFloorTextureWood",title:"Wood Floor Preview",description:"Base and accent colors control the wood grain, seam lines, and directional depth layers."},"Floor Textures \u2014 Marble":{method:"_renderThemePreviewFloorTextureMarble",title:"Marble Floor Preview",description:"Base and accent colors control the marble field and vein layers."},"Floor Textures \u2014 Concrete":{method:"_renderThemePreviewFloorTextureConcrete",title:"Concrete Floor Preview",description:"Base and accent colors control the micro-texture and broad variation layers."},"Floor Textures \u2014 Carpet Low":{method:"_renderThemePreviewFloorTextureCarpetLow",title:"Carpet Low Pile Preview",description:"Base color tints the low-pile carpet texture layer on the card surface."},"Floor Textures \u2014 Carpet High":{method:"_renderThemePreviewFloorTextureCarpetHigh",title:"Carpet High Pile Preview",description:"Base color tints the high-pile carpet texture layer on the card surface."},"Floor Textures \u2014 Granite":{method:"_renderThemePreviewFloorTextureGranite",title:"Granite Floor Preview",description:"Base color tints the granite texture layer on the card surface."},"Queue & Ordering":{method:"_renderThemePreviewQueueOrdering",title:"Queue & Ordering Preview",description:"Queue strip, order chips, and drag feedback samples show sequencing and reorder states."},"Status, Confidence & Alerts":{method:"_renderThemePreviewStatusAlerts",title:"Status & Alerts Preview",description:"Status dots, confidence badges, and alert surfaces show semantic state color relationships."},"Learning & Metrics":{method:"_renderThemePreviewLearningMetrics",title:"Learning & Metrics Preview",description:"Estimate badges and learning panels preview predictive and analytical surfaces."},"Modals & Overlays":{method:"_renderThemePreviewModalsOverlays",title:"Modal & Overlay Preview",description:"A modal shell sample isolates overlay surfaces, chips, warning states, and backdrop treatment."},"Shared Foundations":{method:"_renderThemePreviewSharedFoundations",title:"Shared Foundations Preview",description:"A mixed control-surface preview shows spacing, radius, motion, and typography primitives together."}});function Nr(i){i._renderThemePreviewPane=function(){let e=this.card._state.currentThemePreviewGroup(),t=Or[e];if(!t)return"";let r=typeof this[t.method]=="function"?this[t.method]():"";return r?`
      <aside class="evcc-theme-preview-column">
        <section class="evcc-theme-preview-pane">
          <div class="evcc-theme-preview-header">
            <div class="evcc-theme-preview-eyebrow">Contextual Preview</div>
            <div class="evcc-theme-preview-title">
              ${this.escapeHtml(t.title)}
            </div>
            <div class="evcc-theme-preview-description">
              ${this.escapeHtml(t.description)}
            </div>
          </div>

          <div class="evcc-theme-preview-body">
            ${r}
          </div>
        </section>
      </aside>
    `:""},i._renderThemePreviewShellTypography=function(){return`
      <div class="evcc-theme-preview-grid evcc-theme-preview-grid--shell">
        <section class="evcc-theme-preview-card evcc-theme-preview-card--hero">
          <div class="evcc-theme-preview-shell-kicker">EVCC Shell</div>
          <h2 class="evcc-theme-preview-heading">Premium vacuum control, calmly organized.</h2>
          <p class="evcc-theme-preview-copy">
            Primary and secondary text plus accent styling define the card\u2019s voice before any specific feature surface appears.
          </p>
          <div class="evcc-theme-preview-inline-actions">
            <span class="evcc-theme-preview-linkish">Open Metrics</span>
            <span class="evcc-theme-preview-accent-pill">Accent</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Text Stack</div>
          <div class="evcc-theme-preview-text-stack">
            <div class="evcc-theme-preview-text-primary">Primary text anchors the main reading path.</div>
            <div class="evcc-theme-preview-text-secondary">Secondary text supports controls and summaries without overpowering them.</div>
            <div class="evcc-theme-preview-text-muted">Muted text handles metadata, helper copy, and low-priority hints.</div>
          </div>
        </section>
      </div>
    `},i._renderThemePreviewCardsSurfaces=function(){return`
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Raised Card</div>
          <div class="evcc-theme-preview-surface-card">
            <div class="evcc-theme-preview-surface-title">Card Surface</div>
            <div class="evcc-theme-preview-text-secondary">Shared card background, gap, padding, and surface treatment.</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Panel + Input</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-text-secondary">Panel surfaces and nested inputs preview layered elevation.</div>
            <div class="evcc-theme-preview-input">Search tokens...</div>
          </div>
        </section>
      </div>
    `},i._renderThemePreviewBordersShadows=function(){return`
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Border Strength</div>
          <div class="evcc-theme-preview-border-stack">
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--subtle">Subtle border</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--default">Default border</div>
            <div class="evcc-theme-preview-border-sample evcc-theme-preview-border-sample--strong">Strong border</div>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Shadow Depth</div>
          <div class="evcc-theme-preview-shadow-stack">
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--card">Card shadow</div>
            <div class="evcc-theme-preview-shadow-sample evcc-theme-preview-shadow-sample--hover">Hover shadow</div>
          </div>
        </section>
      </div>
    `},i._renderThemePreviewChips=function(){return`
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">Chip Matrix</div>
        <div class="evcc-theme-preview-chip-grid">
          <span class="evcc-chip">Default</span>
          <span class="evcc-chip active">Active</span>
          <span class="evcc-chip evcc-theme-preview-chip--hover">Hover</span>
          <span class="evcc-chip evcc-theme-preview-chip--included">Included</span>
          <span class="evcc-chip evcc-theme-preview-chip--excluded">Excluded</span>
          <span class="evcc-chip evcc-theme-preview-chip--success">Success</span>
          <span class="evcc-chip evcc-theme-preview-chip--warning">Warning</span>
        </div>
      </div>
    `},i._renderThemePreviewRoomCards=function(){return`
      <div class="evcc-theme-preview-grid evcc-theme-preview-grid--rooms">
        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Kitchen</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#1</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Profile</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip">Daily Vacuum</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Room</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">Hardwood</span>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card evcc-theme-preview-room-card--filled">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Hallway</div>
            <span class="evcc-chip evcc-theme-preview-room-order">#2</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Profile</span>
            <span class="evcc-chip evcc-theme-preview-profile-chip evcc-theme-preview-profile-chip--custom">Custom Profile</span>
          </div>

          <div class="evcc-theme-preview-room-detail-row">
            <span class="evcc-theme-preview-detail-label">Room</span>
            <span class="evcc-chip evcc-theme-preview-room-chip">Area Rug</span>
          </div>
        </section>
      </div>
    `},i._renderThemePreviewFloorTextures=function(){return`<div class="evcc-theme-preview-ftx-card-grid">${[{key:"tile",name:"Tile"},{key:"wood",name:"Wood"},{key:"marble",name:"Marble"},{key:"concrete",name:"Concrete"},{key:"carpet_low",name:"Carpet Low"},{key:"carpet_high",name:"Carpet High"},{key:"granite_light",name:"Granite"}].map(({key:r,name:a})=>this._renderFloorPreviewCard(r,a)).join("")}</div>`},i._renderFloorPreviewCard=function(e,t){return this.renderRoomCard({id:`preview-ftx-${e}`,name:t??e,floor_type:e,enabled:!0,order:1},null)},i._renderThemePreviewFloorTextureTile=function(){return this._renderFloorPreviewCard("tile","Tile")},i._renderThemePreviewFloorTextureWood=function(){return this._renderFloorPreviewCard("wood","Wood")},i._renderThemePreviewFloorTextureMarble=function(){return this._renderFloorPreviewCard("marble","Marble")},i._renderThemePreviewFloorTextureConcrete=function(){return this._renderFloorPreviewCard("concrete","Concrete")},i._renderThemePreviewFloorTextureCarpetLow=function(){return this._renderFloorPreviewCard("carpet_low","Carpet Low")},i._renderThemePreviewFloorTextureCarpetHigh=function(){return this._renderFloorPreviewCard("carpet_high","Carpet High")},i._renderThemePreviewFloorTextureGranite=function(){return this._renderFloorPreviewCard("granite_light","Granite")},i._renderThemePreviewQueueOrdering=function(){return`
      <div class="evcc-theme-preview-card">
        <div class="evcc-theme-preview-section-title">Queue Strip</div>
        <div class="evcc-theme-preview-queue-strip">
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--current">
            <span class="evcc-chip evcc-theme-preview-order-chip">1</span>
            Kitchen
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--pending">
            <span class="evcc-chip evcc-theme-preview-order-chip">2</span>
            Cat Room
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--completed">
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
            Entry
          </div>
          <div class="evcc-theme-preview-queue-chip evcc-theme-preview-queue-chip--inferred">
            <span class="evcc-chip evcc-theme-preview-order-chip">4</span>
            Office
          </div>
        </div>

        <div class="evcc-theme-preview-reorder-row">
          <div class="evcc-theme-preview-drag-card">Dragging</div>
          <div class="evcc-theme-preview-order-target">Drop target</div>
        </div>
      </div>
    `},i._renderThemePreviewStatusAlerts=function(){return`
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Status Dots</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--idle">Idle</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">Cleaning</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--docked">Docked</span>
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--error">Error</span>
          </div>
        </section>

        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Confidence & Alerts</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-confidence-high">High confidence</span>
            <span class="evcc-chip evcc-theme-preview-confidence-medium">Medium confidence</span>
            <span class="evcc-chip evcc-theme-preview-confidence-low">Low confidence</span>
          </div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--info">Information surface</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">Warning surface</div>
          <div class="evcc-theme-preview-alert evcc-theme-preview-alert--error">Error surface</div>
        </section>
      </div>
    `},i._renderThemePreviewLearningMetrics=function(){return`
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card">
          <div class="evcc-theme-preview-section-title">Estimate Badges</div>
          <div class="evcc-theme-preview-chip-grid">
            <span class="evcc-chip evcc-theme-preview-estimate-default">~18 min default</span>
            <span class="evcc-chip evcc-theme-preview-estimate-learned">~14 min learned</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-high">High confidence</span>
            <span class="evcc-chip evcc-theme-preview-learning-confidence-medium">Building confidence</span>
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">Learning Panel</div>
          <div class="evcc-theme-preview-text-primary">Estimated water use: 410 ml</div>
          <div class="evcc-theme-preview-text-secondary">Tank after run: 850 ml (28%)</div>
          <div class="evcc-theme-preview-note">Re-anchor suggested after a long interrupted run.</div>
        </section>
      </div>
    `},i._renderThemePreviewModalsOverlays=function(){return`
      <div class="evcc-theme-preview-modal-stage">
        <div class="evcc-theme-preview-modal-backdrop"></div>
        <div class="evcc-theme-preview-modal">
          <div class="evcc-theme-preview-modal-header">
            <div>
              <div class="evcc-theme-preview-modal-title">Maintenance Reset</div>
              <div class="evcc-theme-preview-text-muted">Overlay shell preview</div>
            </div>
            <span class="evcc-chip">X</span>
          </div>

          <div class="evcc-theme-preview-modal-body">
            <div class="evcc-chip evcc-theme-preview-modal-accent-chip">Accent chip</div>
            <div class="evcc-theme-preview-input">Type a note...</div>
            <div class="evcc-theme-preview-alert evcc-theme-preview-alert--warning">This action cannot be undone.</div>
          </div>

          <div class="evcc-theme-preview-modal-footer">
            <span class="evcc-chip">Cancel</span>
            <span class="evcc-chip evcc-chip--save">Confirm</span>
          </div>
        </div>
      </div>
    `},i._renderThemePreviewSharedFoundations=function(){return`
      <div class="evcc-theme-preview-grid">
        <section class="evcc-theme-preview-card evcc-theme-preview-foundation-card">
          <div class="evcc-theme-preview-section-title">Surface Stack</div>
          <div class="evcc-theme-preview-surface-panel">
            <div class="evcc-theme-preview-input">Foundation input</div>
            <div class="evcc-theme-preview-chip-grid">
              <span class="evcc-chip">Chip</span>
              <span class="evcc-chip active">Active</span>
            </div>
          </div>
        </section>

        <section class="evcc-theme-preview-room-card">
          <div class="evcc-theme-preview-room-header">
            <div class="evcc-theme-preview-room-name">Mixed Surface</div>
            <span class="evcc-chip evcc-theme-preview-order-chip">3</span>
          </div>
          <div class="evcc-theme-preview-text-secondary">
            Shared gap, radius, font, hover lift, and transition values show up here together.
          </div>
        </section>

        <section class="evcc-theme-preview-learning-panel">
          <div class="evcc-theme-preview-section-title">Composite Sample</div>
          <div class="evcc-theme-preview-status-dots">
            <span class="evcc-theme-preview-status-dot evcc-theme-preview-status-dot--cleaning">Cleaning</span>
          </div>
          <div class="evcc-theme-preview-copy">
            Foundations touch multiple systems, so the preview intentionally mixes a few representative surfaces.
          </div>
        </section>
      </div>
    `}}function wi(i){switch(i){case"cleaning":return"alert";case"returning":return"walking";case"paused":return"standing";case"error":return"warning";case"docked":case"idle":return"curled";default:return"curled"}}function Fr(i){let e=0,t=0,r=0,a=i.length;for(let n=0,c=a-1;n<a;c=n++){let s=i[c][0]*i[n][1]-i[n][0]*i[c][1];e+=s,t+=(i[c][0]+i[n][0])*s,r+=(i[c][1]+i[n][1])*s}if(e*=.5,Math.abs(e)<1e-10){let n=i.reduce((s,o)=>s+o[0],0),c=i.reduce((s,o)=>s+o[1],0);return[n/a,c/a]}return[t/(6*e),r/(6*e)]}var Le=["#00e5ff","#ff6b35","#a3e635","#e879f9","#fbbf24","#a78bfa","#fb7185","#34d399","#60a5fa","#f472b6","#4ade80","#f97316"],Si=[{key:"dark",label:"Dark",hint:"primary \u2014 clearest room colours"},{key:"light",label:"Light",hint:"assist \u2014 wall detection"},{key:"default",label:"Default",hint:"fallback"}];function Hr(i){i.renderMapRoomView=function(e){let{state:t,vacuumStatus:r}=e,a=t.mapSegmentsData(),n=t.mapImageUrl();if(!a?.available||!n)return`
        <div class="evcc-map-view">
          <div class="evcc-map-unavailable">
            <p>No map image available.</p>
            <p class="evcc-map-unavailable-hint">Upload and analyze a map image to enable map view.</p>
          </div>
        </div>
      `;let c=t.mapSegments(),s=t.selectedSegmentIds(),o=t.selectedSegments(),l=t.getRoomsForActiveMap?.()??[],d=c.map(p=>{let f=t.roomIdForSegment(p.segment_id),h=f!=null?l.find(y=>String(y.id)===String(f)):null;return typeof this._resolveSegmentFloorType=="function"?this._resolveSegmentFloorType(h):"default"}),u=t.mapZoom?.()??1,v=t.mapTranslateX?.()??0,m=t.mapTranslateY?.()??0;return`
      <div class="evcc-map-view">
        <div class="evcc-map-container">

          <div class="evcc-map-layers" style="transform:translate(${v}px,${m}px) scale(${u});transform-origin:0 0">
            <img
              class="evcc-map-image"
              src="${this.escapeHtml(n)}"
              alt="Floor plan"
              draggable="false"
            >
            <svg
              class="evcc-map-svg"
              viewBox="0 0 100 100"
              preserveAspectRatio="xMidYMid meet"
            >
              ${typeof this._buildFloorTextureDefs=="function"?this._buildFloorTextureDefs(d):""}
              ${c.map((p,f)=>{let h=t.roomIdForSegment(p.segment_id),y=h!=null?l.find(g=>String(g.id)===String(h)):null,x=y?.name??p.name??p.label??`Segment ${p.segment_id}`,w=y?"Tap to queue \xB7 Double-tap to configure":"Tap to queue";return this._renderMapSegmentPolygon(p,s,f,x,w)}).join("")}
              ${typeof this._renderFloorTexturePolygon=="function"?c.map((p,f)=>this._renderFloorTexturePolygon(p,d[f])).join(""):""}
              <circle class="evcc-map-debug-origin" cx="0" cy="0" r="1.5"/>
            </svg>
            ${this._renderMapAnimal(t,r)}
            ${c.map(p=>{let f=p.polygon_pct;if(!Array.isArray(f)||f.length<3)return"";let[h,y]=Fr(f),x=Math.min(Math.max(h,5),95),w=Math.min(Math.max(y,6),94),g=t.roomIdForSegment(p.segment_id),S=(g!=null?l.find(W=>String(W.id)===String(g)):null)?.name??p.name??p.label??null;if(!S)return"";let P=o.findIndex(W=>String(W.segment_id)===String(p.segment_id)),O=P>=0;return`<div class="evcc-map-label${O?" evcc-map-label--selected":""}" style="left:${x}%;top:${w}%">
                ${O?`<span class="evcc-map-label-order">${P+1}</span>`:""}
                <span class="evcc-map-label-name">${this.escapeHtml(S)}</span>
              </div>`}).join("")}
          </div>

          <div class="evcc-map-tooltip" aria-hidden="true"></div>

        </div>

      </div>
    `},i._renderMapSegmentPolygon=function(e,t,r,a,n){let c=e.polygon_pct;if(!Array.isArray(c)||c.length<3)return"";let s=t.has(String(e.segment_id)),o=Le[r%Le.length],l=c.map(([d,u])=>`${d},${u}`).join(" ");return`<polygon
      class="evcc-map-polygon${s?" evcc-map-polygon--selected":""}"
      points="${l}"
      style="--seg-color:${o}"
      data-action="toggle-segment"
      data-segment-id="${this.escapeHtml(String(e.segment_id))}"
      data-label="${this.escapeHtml(a??"")}"
      data-hint="${this.escapeHtml(n??"")}"
    />`},i._renderMapAnimal=function(e,t){let r=e.mapSegments(),a=e.getRoomsForActiveMap?.()??[],n=null,c=g=>{if(g==null)return null;let R=e.segmentIdForRoom?.(g);return R==null?null:r.find(S=>String(S.segment_id)===String(R))??null};if(t==="docked"||t==="idle"){let g=a.find(R=>R.isDockRoom);n=c(g?.id)}if(!n){let g=e.dashboardJobProgress?.(),R=g?.position_room_id??g?.current_room_id;n=c(R)}if(n||(n=r[0]??null),!n)return"";let o=e.roomIdForSegment(n.segment_id),l=o!=null?String(o):`seg_${n.segment_id}`,d,u,v=e.roomDotAnchor?.(l);if(v)d=v.pct_x,u=v.pct_y;else{let g=n.polygon_pct;if(!Array.isArray(g)||g.length<3)return"";[d,u]=Fr(g)}let m=wi(t??""),p=m==="curled",f=e.mapAnimalSelection?.()??"cat",h=e.mapAnimalScale?.()??1,y=o!=null?String(o):`seg_${n.segment_id}`,x=Math.round(64*h),w=Math.round(44*h);return`<div
      class="evcc-map-animal${p?" evcc-map-animal--pulse":""}"
      style="left:${d}%;top:${u}%;width:${x}px;height:${w}px"
      data-action="map-dot-click"
      data-anchor-key="${this.escapeHtml(y)}"
      title="Drag to reposition"
    ><animal-svg animal="${this.escapeHtml(f)}" pose="${this.escapeHtml(m)}" width="${x}px" height="${w}px"></animal-svg></div>`},i._renderMapSelectionBar=function(e,t){let r=t.getRoomsForActiveMap?.()??[];return`<div class="evcc-map-selection-bar">${e.map((n,c)=>{let s=t.roomIdForSegment(n.segment_id),o=s!=null?r.find(u=>String(u.id)===String(s)):null,l=o?.name??n.name??n.label??`Segment ${n.segment_id}`,d=o?this._mapRoomSettingsSummary(o):"";return`
        <div
          class="evcc-map-chip"
          data-action="map-chip-activate"
          data-segment-id="${this.escapeHtml(String(n.segment_id))}"
          data-room-id="${s!=null?this.escapeHtml(String(s)):""}"
        >
          <span class="evcc-map-chip-order">${c+1}</span>
          <div class="evcc-map-chip-body">
            <span class="evcc-map-chip-label">${this.escapeHtml(l)}</span>
            ${d?`<span class="evcc-map-chip-settings">${this.escapeHtml(d)}</span>`:""}
          </div>
        </div>
      `}).join("")}</div>`},i._mapRoomSettingsSummary=function(e){let t=[];return e.fanSpeed&&t.push(e.fanSpeed),e.waterLevel&&t.push(e.waterLevel),t.join(" \xB7 ")},i.renderMapConfigView=function(e){let{state:t}=e,r=t.mapSegmentsData(),a=t.mapImageUrl(),n=t.mapSegments(),c=t.configSelectedSegmentId(),s=t.configSelectedSegment(),o=r?.image_variants??{},l=r?.summary??{},d=t.mapActionStatus?.()??null;return`
      <div class="evcc-map-config-view">

        <div class="evcc-map-config-header">
          <button class="evcc-map-config-back" data-action="map-config-back" aria-label="Back to rooms">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="10,3 4,8 10,13"/>
            </svg>
            Rooms
          </button>
          <span class="evcc-map-config-title">Map Configuration</span>
        </div>

        <div class="evcc-map-config-body">

          <div class="evcc-map-container evcc-map-container--config">
            ${a?`<img class="evcc-map-image" src="${this.escapeHtml(a)}" alt="Floor plan" draggable="false">
                 <svg class="evcc-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                   ${n.map((u,v)=>{let m=String(u.segment_id)===String(c??"");return this._renderConfigPolygon(u,c,v,m?t.configSelectedVertexIndex?.()??null:null)}).join("")}
                 </svg>`:`<div class="evcc-map-unavailable">
                   <p>No map image uploaded yet.</p>
                 </div>`}
          </div>

          <div class="evcc-map-config-side-panel">
            ${s?this._renderSegmentAdjustSection(s,t):`<div class="evcc-map-config-section evcc-map-config-section--hint">
                   <p>Click a segment on the map to adjust it.</p>
                 </div>`}
          </div>

        </div>

        <div class="evcc-map-config-panel">
          ${this._renderVariantsSection(o,l,d)}
        </div>

      </div>
    `},i._renderConfigPolygon=function(e,t,r,a){let n=e.polygon_pct;if(!Array.isArray(n)||n.length<3)return"";let c=String(e.segment_id)===String(t??""),s=Le[r%Le.length],o=n.map(([v,m])=>`${v},${m}`).join(" "),l=this.escapeHtml(String(e.segment_id)),d=`<polygon
      class="evcc-map-polygon evcc-map-polygon--config"
      points="${o}"
      style="fill:${s};fill-opacity:${c?"0.20":"0.06"};stroke:${c?"#ffffff":s};stroke-width:${c?"0.8":"0.4"};stroke-opacity:${c?"1":"0.7"}"
      data-action="config-select-segment"
      data-segment-id="${l}"
    />`,u="";return c&&(u=n.map(([v,m],p)=>{let f=a===p;return`<circle
          class="evcc-map-vertex-dot${f?" evcc-map-vertex-dot--selected":""}"
          cx="${v}" cy="${m}" r="${f?"1.8":"0.9"}"
          style="fill:${f?"#ffdd00":s};stroke:${f?"#000":"rgba(0,0,0,0.55)"};stroke-width:0.25;pointer-events:all;cursor:pointer"
          data-action="select-vertex"
          data-segment-id="${l}"
          data-vertex-index="${p}"
        />`}).join("")),`<g>${d}${u}</g>`},i._renderVariantsSection=function(e,t,r){let a=Si.map(({key:l,label:d,hint:u})=>{let v=e[l],m=r?.type==="upload"&&r?.variant===l&&r?.status==="busy",p=r?.type==="upload"&&r?.variant===l&&r?.status==="error",f=v?`${v.width} \xD7 ${v.height}`:"not uploaded",h=v?"evcc-map-variant-status--ok":"evcc-map-variant-status--missing";return`
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">${this.escapeHtml(d)}</span>
            <span class="evcc-map-variant-hint">${this.escapeHtml(u)}</span>
          </div>
          <span class="evcc-map-variant-status ${h}">${f}</span>
          ${p?`<span class="evcc-map-action-status evcc-map-action-status--error">
                 ${this.escapeHtml(r.message??"Upload failed")}
               </span>`:""}
          <button
            class="evcc-map-config-btn${m?" evcc-map-config-btn--busy":""}"
            data-action="upload-map-variant"
            data-variant="${l}"
            ${m?"disabled":""}
          >${m?"Uploading\u2026":"Upload"}</button>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/bmp"
            data-variant-input="${l}"
            style="display:none"
          >
        </div>
      `}).join(""),n=t.segment_count??t.count??0,c=t.adjusted_count??0,s=r?.type==="analyze"&&r?.status==="busy",o=r?.type==="analyze"&&r?.status==="error";return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Image Variants</div>
        ${a}
        <div class="evcc-map-config-analyze-row">
          <span class="evcc-map-config-seg-count">
            ${o?`<span class="evcc-map-action-status evcc-map-action-status--error">
                   ${this.escapeHtml(r.message??"Analysis failed")}
                 </span>`:n>0?`${n} segments${c>0?`, ${c} adjusted`:""}`:"No segments analysed"}
          </span>
          <button
            class="evcc-map-config-btn evcc-map-config-btn--primary${s?" evcc-map-config-btn--busy":""}"
            data-action="analyze-map"
            ${s?"disabled":""}
          >${s?"Analysing\u2026":n>0?"Re-analyse":"Analyse map"}</button>
        </div>
      </div>
    `},i._renderSegmentAdjustSection=function(e,t){let r=e.name??e.label??`Segment ${e.segment_id}`,a=this.escapeHtml(String(e.segment_id));return`
      ${this._renderTranslationSection(e,t,a,r)}
      ${this._renderEdgeSection(e,t,a)}
      ${this._renderVertexSection(e,t,a)}
      ${this._renderRoomAssignSection(e,t)}
    `},i._renderTranslationSection=function(e,t,r,a){let n=t.mapNudgeStep(),c=e.translation_offset,s=Array.isArray(c)?c[0]??0:c?.x??0,o=Array.isArray(c)?c[1]??0:c?.y??0;return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">
          Adjusting: <em>${this.escapeHtml(a)}</em>
        </div>
        <div class="evcc-map-config-adj-meta">Offset: ${s} px, ${o} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${r}" data-dx="0" data-dy="-${n.y}" title="Nudge up">\u2191</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${r}" data-dx="-${n.x}" data-dy="0" title="Nudge left">\u2190</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-segment-adjustment"
              data-segment-id="${r}" title="Reset translation">\u25CB</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${r}" data-dx="${n.x}" data-dy="0" title="Nudge right">\u2192</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${r}" data-dx="0" data-dy="${n.y}" title="Nudge down">\u2193</button>
          </div>
        </div>
      </div>
    `},i._renderEdgeSection=function(e,t,r){let a=t.mapNudgeStep(),n=e.edge_adjustment??{};return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Edges</div>
        <div class="evcc-map-edge-grid">${[{key:"top",label:"Top",stepKey:"y"},{key:"bottom",label:"Bottom",stepKey:"y"},{key:"left",label:"Left",stepKey:"x"},{key:"right",label:"Right",stepKey:"x"}].map(({key:o,label:l,stepKey:d})=>{let u=n[o]??0,v=a[d];return`
        <div class="evcc-map-edge-row">
          <span class="evcc-map-edge-label">${l}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${r}"
            data-edge="${o}" data-delta="-${v}" title="Contract ${l}">\u2212</button>
          <span class="evcc-map-edge-val">${u>0?"+":""}${u}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${r}"
            data-edge="${o}" data-delta="${v}" title="Expand ${l}">+</button>
        </div>
      `}).join("")}</div>
      </div>
    `},i._renderVertexSection=function(e,t,r){let a=e.polygon_pct??e.polygon_pixel??[],n=e.vertex_adjustment??[],c=t.configSelectedVertexIndex?.(),s=t.mapNudgeStep();if(a.length===0)return"";let o={};n.forEach(u=>{o[u.index]=u});let l=a.map((u,v)=>{let m=c===v,p=o[v]!=null,f="evcc-map-vertex-chip";return m&&(f+=" evcc-map-vertex-chip--selected"),p&&(f+=" evcc-map-vertex-chip--adjusted"),`<button class="${f}" data-action="select-vertex"
        data-segment-id="${r}" data-vertex-index="${v}">${v}</button>`}).join(""),d="";if(c!=null&&c<a.length){let u=o[c],v=u?.delta_x??0,m=u?.delta_y??0;d=`
        <div class="evcc-map-config-adj-meta">V${c}: ${v>=0?"+":""}${v}, ${m>=0?"+":""}${m} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${r}" data-vertex-index="${c}"
              data-dx="0" data-dy="-${s.y}" title="Nudge vertex up">\u2191</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${r}" data-vertex-index="${c}"
              data-dx="-${s.x}" data-dy="0" title="Nudge vertex left">\u2190</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-vertex"
              data-segment-id="${r}" data-vertex-index="${c}"
              title="Reset this vertex">\u25CB</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${r}" data-vertex-index="${c}"
              data-dx="${s.x}" data-dy="0" title="Nudge vertex right">\u2192</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${r}" data-vertex-index="${c}"
              data-dx="0" data-dy="${s.y}" title="Nudge vertex down">\u2193</button>
          </div>
        </div>
      `}return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Vertices</div>
        <div class="evcc-map-vertex-chips">${l}</div>
        ${d}
      </div>
    `},i._renderRoomAssignSection=function(e,t){let r=t.getRoomsForActiveMap?.()??[],a=t.roomIdForSegment(e.segment_id),n=this.escapeHtml(String(e.segment_id));return r.length===0?"":`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Link to room</div>
        <div class="evcc-map-room-assign-chips">${r.map(s=>{let o=a!=null&&String(s.id)===String(a),l=!o&&t.segmentIdForRoom(s.id)!=null,d="evcc-map-room-assign-chip";return o&&(d+=" evcc-map-room-assign-chip--linked"),l&&(d+=" evcc-map-room-assign-chip--taken"),`
        <button
          class="${d}"
          data-action="assign-segment-room"
          data-segment-id="${n}"
          data-room-id="${this.escapeHtml(String(s.id))}"
          ${l?"disabled":""}
          title="${l?"Already linked to another segment":o?`Unlink ${this.escapeHtml(s.name)}`:`Link to ${this.escapeHtml(s.name)}`}"
        >${this.escapeHtml(s.name)}${o?" \u2713":""}</button>
      `}).join("")}</div>
      </div>
    `}}var N="/eufy_vacuum/textures",Pe={tile:{opacityDefault:1,layers:[{url:`${N}/tile/tile-mask.png`,role:"base",colorToken:"--evcc-floor-tile-base",colorDefault:"#D4AF37",opacityToken:"--evcc-floor-tile-face-opacity",opacityDefault:.87},{url:`${N}/tile/grout-mask.png`,role:"grout",colorToken:"--evcc-floor-tile-grout",colorDefault:"#121212",opacityToken:"--evcc-floor-tile-grout-opacity",opacityDefault:.95},{url:`${N}/tile/pure-tile-grout.png`,role:"accent",colorToken:"--evcc-floor-tile-accent",colorDefault:"#f0f0f5",opacityToken:"--evcc-floor-tile-line-opacity",opacityDefault:.39}],masks:[{url:`${N}/tile/tile-mask.png`},{url:`${N}/tile/grout-mask.png`},{url:`${N}/tile/pure-tile-grout.png`}],baseTexture:null},wood:{opacityDefault:.99,layers:[{url:`${N}/wood/wood-directional-depth-mask.png`,role:"base",colorToken:"--evcc-floor-wood-base",colorDefault:"#7A4010cf",opacityToken:"--evcc-floor-wood-depth-opacity",opacityDefault:.43},{url:`${N}/wood/wood-grain-mask.png`,role:"base",colorToken:"--evcc-floor-wood-base",colorDefault:"#7A4010cf",opacityToken:"--evcc-floor-wood-grain-opacity",opacityDefault:.84},{url:`${N}/wood/wood-seam-mask.png`,role:"accent",colorToken:"--evcc-floor-wood-accent",colorDefault:"#e89754",opacityToken:"--evcc-floor-wood-seam-opacity",opacityDefault:.78}],masks:[{url:`${N}/wood/wood-grain-mask.png`},{url:`${N}/wood/wood-seam-mask.png`},{url:`${N}/wood/wood-directional-depth-mask.png`}],baseTexture:null},marble:{opacityDefault:.9,layers:[{url:`${N}/marble/marble-base-mask.png`,role:"base",colorToken:"--evcc-floor-marble-base",colorDefault:"#e9e8e8",opacityToken:"--evcc-floor-marble-base-opacity",opacityDefault:.97},{url:`${N}/marble/marble-micro-texture-mask.png`,role:"micro",colorToken:"--evcc-floor-marble-micro",colorDefault:"#080707",opacityToken:"--evcc-floor-marble-micro-opacity",opacityDefault:1},{url:`${N}/marble/marble-vein-mask.png`,role:"accent",colorToken:"--evcc-floor-marble-accent",colorDefault:"#D4AF3773",opacityToken:"--evcc-floor-marble-vein-opacity",opacityDefault:0}],masks:[{url:`${N}/marble/marble-vein-mask.png`},{url:`${N}/marble/marble-micro-texture-mask.png`},{url:`${N}/marble/marble-base-mask.png`}],baseTexture:null},concrete:{opacityDefault:1,layers:[{url:`${N}/concrete/concrete-broad-mask.png`,role:"base",colorToken:"--evcc-floor-concrete-base",colorDefault:"#eceaea",opacityToken:"--evcc-floor-concrete-broad-opacity",opacityDefault:1},{url:`${N}/concrete/concrete-micro-mask.png`,role:"accent",colorToken:"--evcc-floor-concrete-accent",colorDefault:"#121111",opacityToken:"--evcc-floor-concrete-micro-opacity",opacityDefault:.62}],masks:[{url:`${N}/concrete/concrete-micro-mask.png`},{url:`${N}/concrete/concrete-broad-mask.png`}],baseTexture:null},carpet_low:{opacityDefault:.8,layers:[{url:`${N}/carpet/texture-floor-carpet-low.png`,role:"base",colorToken:"--evcc-floor-carpet-low-base",colorDefault:"#0d0c0c",opacityToken:"--evcc-floor-carpet-low-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${N}/carpet/texture-floor-carpet-low.png`},carpet_high:{opacityDefault:1,layers:[{url:`${N}/carpet/texture-floor-carpet-high.png`,role:"base",colorToken:"--evcc-floor-carpet-high-base",colorDefault:"#0a0a0a",opacityToken:"--evcc-floor-carpet-high-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${N}/carpet/texture-floor-carpet-high.png`},granite_light:{opacityDefault:1,layers:[{url:`${N}/granite/texture-floor-granite-light.png`,role:"base",colorToken:"--evcc-floor-granite-light-base",colorDefault:"#0a0a0a",opacityToken:"--evcc-floor-granite-light-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${N}/granite/texture-floor-granite-light.png`},default:{opacityDefault:.85,layers:[],masks:[],baseTexture:null}};function Ve(i){let e=Pe[i];return e?e.baseTexture?e.baseTexture:e.layers.length?e.layers[0].url:e.masks.length?e.masks[0].url:null:null}function qe(i){let e=String(i?.floor_type??"").toLowerCase().trim(),t=String(i?.carpet_type??"").toLowerCase().trim();return e==="carpet"?t==="high_pile"||t==="high"?"carpet_high":"carpet_low":e==="carpet_low_pile"||e==="carpet_low"?"carpet_low":e==="carpet_high_pile"||e==="carpet_high"?"carpet_high":e==="hardwood"||e==="laminate"||e==="wood"?"wood":e==="tile"?"tile":e==="marble"?"marble":e==="concrete"?"concrete":e==="granite"||e==="granite_light"?"granite_light":"default"}function Ri(i){let e=String(i??""),t=2166136261;for(let n=0;n<e.length;n++)t^=e.charCodeAt(n),t=Math.imul(t,16777619)>>>0;let r=t%101,a=(t>>>13^t>>>7)%101;return`${r}% ${a}%`}function Dr(i){i._resolveSegmentFloorType=function(e){return qe({floor_type:e?.floor_type??e?.floorType??"",carpet_type:e?.carpet_type??e?.carpetType??""})},i._renderFloorTextureLayer=function(e){let t=qe({floor_type:e?.floorType??"",carpet_type:e?.carpetType??""}),r=Pe[t]??Pe.default,a=r.opacityDefault??.85,n=`var(--evcc-floor-${t}-opacity-card,var(--evcc-floor-texture-opacity-card,${a}))`,c=Ri(e?.id??e?.name??t),s=r.layers.map(o=>{let l=`var(${o.colorToken},${o.colorDefault})`,d=`url(${o.url})`,u=`var(${o.opacityToken},${o.opacityDefault})`;return`<span class="evcc-ftx-layer" data-role="${o.role}" style="background-color:${l};mask-image:${d};-webkit-mask-image:${d};--layer-opacity:${u}"></span>`}).join("");return`<div class="evcc-room-texture-layer" data-floor="${t}" style="--floor-opacity-card:${n};--floor-position-card:${c}">${s}</div>`},i._buildFloorTextureDefs=function(e){let t=new Set,r=[];for(let a of e){if(t.has(a))continue;t.add(a);let n=Ve(a);n&&r.push(`<pattern id="evcc-ftx-${a}" patternUnits="userSpaceOnUse" width="8" height="8"><image href="${n}" width="8" height="8" preserveAspectRatio="xMidYMid slice"/></pattern>`)}return r.length?`<defs>${r.join("")}</defs>`:""},i._renderFloorTexturePolygon=function(e,t){let r=e.polygon_pct;return!Array.isArray(r)||r.length<3||!Ve(t)?"":`<polygon class="evcc-map-texture-polygon" points="${r.map(([n,c])=>`${n},${c}`).join(" ")}" fill="url(#evcc-ftx-${t})" data-floor="${t}"/>`}}var Ei=[{value:"hardwood",label:"Hardwood"},{value:"laminate",label:"Laminate"},{value:"tile",label:"Tile"},{value:"marble",label:"Marble"},{value:"granite",label:"Granite"},{value:"concrete",label:"Concrete"},{value:"carpet_low_pile",label:"Low-Pile Carpet"},{value:"carpet_high_pile",label:"High-Pile Carpet"}];function Br(i){i.renderSetupView=function(e){let{state:t,card:r}=e,a=r._config?.vacuum_entity_id??"",n=t.setupStatus?.()??null,c=t.setupLoading?.()??!1,s=t.setupError?.()??null,o=t.setupLastResult?.()??null,d=(Array.isArray(n?.vacuums)?n.vacuums:[]).find(M=>M.vacuum_entity_id===a)??null,u=d!=null,v=(d?.maps??[]).filter(M=>M.imported),m=v.length>0,p=m&&v.every(M=>t.isSetupMapConfigured?.(String(M.map_id))),f=t.setupRoomEditorOpenMapId?.()??null,h=t.setupRoomEditorLoadingMapId?.()??null,y=t.setupRoomEditorRooms?.()??[],x=t.setupRoomEditorSaving?.()??!1,w=t.setupDeletePendingMapId?.()??null,g=t.setupDeleteStage?.()??null,R=t.setupDeleteTypedToken?.()??"",S=t.setupDeleteDeleting?.()??!1,P=new Set((t.setupRoomEditorEnabledIds?.()??[]).map(String)),O=t.setupRoomEditorFloorTypesMap?.()??{},W=c?'<div class="evcc-setup-result info">Working\u2026</div>':"",ae=s&&!c?`<div class="evcc-setup-result error">${this.escapeHtml(String(s))}</div>`:"",oe=(()=>{if(!o||c)return"";let M=o.status??"",C=o.message??"";return M==="error"||M==="blocked"?`<div class="evcc-setup-result error">${this.escapeHtml(C)}</div>`:`<div class="evcc-setup-result success">${this.escapeHtml(C)}</div>`})(),H=`
      <div class="evcc-setup-step">
        <div class="evcc-setup-step-header">
          <div class="evcc-setup-step-badge ${u?"done":""}">
            ${u?"\u2713":"1"}
          </div>
          <div class="evcc-setup-step-label">Add Vacuum</div>
        </div>

        <div class="evcc-setup-step-body">
          Register this vacuum with the integration so it can be managed.
          <div class="evcc-setup-entity-id">${this.escapeHtml(a)}</div>
        </div>

        ${u?'<div class="evcc-setup-result success">Vacuum registered.</div>':`<button class="evcc-setup-btn"
                     data-action="setup-add-vacuum"
                     ${c?"disabled":""}>
               Add Vacuum
             </button>`}
      </div>
    `,se=M=>h===M?`<div class="evcc-setup-room-editor">
          <div class="evcc-setup-result info">Loading rooms\u2026</div>
        </div>`:f!==M?"":`
        <div class="evcc-setup-room-editor">
          <div class="evcc-setup-room-editor-hint">
            Deselect ghost rooms (Eufy sometimes reports phantom rooms).
            Set each real room's floor type \u2014 it drives the cleaning profile system.
          </div>
          <div class="evcc-setup-room-list">
            ${y.length===0?'<div class="evcc-setup-step-body muted">No rooms found for this map.</div>':y.map(j=>{let V=String(j.room_id),le=this.escapeHtml(j.name??`Room ${V}`),U=P.has(V),ue=O[V]??"hardwood",ne=Ei.map(me=>`
              <button class="evcc-setup-floor-chip ${ue===me.value?"active":""}"
                      data-action="setup-set-floor-type"
                      data-room-id="${V}"
                      data-floor-type="${me.value}"
                      ${x?"disabled":""}>
                ${me.label}
              </button>
            `).join("");return`
              <div class="evcc-setup-room-row ${U?"":"excluded"}">
                <div class="evcc-setup-room-row-top">
                  <button class="evcc-setup-room-toggle ${U?"on":"off"}"
                          data-action="setup-toggle-room"
                          data-room-id="${V}"
                          title="${U?"Click to exclude":"Click to include"}"
                          ${x?"disabled":""}>
                    ${U?"\u2713":"\u2715"}
                  </button>
                  <span class="evcc-setup-room-name">${le}</span>
                </div>
                ${U?`<div class="evcc-setup-floor-chips">${ne}</div>`:""}
              </div>
            `}).join("")}
          </div>
          <button class="evcc-setup-btn"
                  data-action="setup-save-rooms"
                  data-map-id="${M}"
                  ${x?"disabled":""}>
            ${x?"Saving\u2026":"Save Room Configuration"}
          </button>
        </div>
      `,X=(M,C)=>{if(w!==M)return"";let j=this.escapeHtml(C?.typed_confirmation_value??`Map ${M}`),V=C?.requires_typed_confirmation??!1,le=C?.protection_level??"normal",U=C?.reasons??[],ue=U.length?`<div class="evcc-setup-delete-badges">
             ${U.map(He=>`<span class="evcc-setup-protection-badge">${this.escapeHtml(He.message)}</span>`).join("")}
           </div>`:"",ne=V?`<div class="evcc-setup-delete-typed">
             <div class="evcc-setup-delete-typed-hint">
               Type <strong>${j}</strong> to confirm deletion.
             </div>
             <input class="evcc-setup-delete-input"
                    data-action="setup-delete-map-input"
                    type="text"
                    placeholder="${j}"
                    value="${this.escapeHtml(R)}"
                    autocomplete="off"
                    spellcheck="false" />
           </div>`:"",me=V?R.trim()===(C?.typed_confirmation_value??"").trim():!0;return`
        <div class="evcc-setup-delete-panel">
          ${ue}
          <div class="evcc-setup-delete-warning">
            Delete <strong>${j}</strong>? This removes all rooms, history,
            and learning data for this map from the integration.
            Eufy's upstream map is not affected.
          </div>
          ${ne}
          <div class="evcc-setup-delete-actions">
            <button class="evcc-setup-btn destructive small"
                    data-action="setup-delete-map-confirm"
                    data-map-id="${M}"
                    ${!me||S?"disabled":""}>
              ${S?"Deleting\u2026":"Delete Map"}
            </button>
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-delete-map-cancel"
                    ${S?"disabled":""}>
              Cancel
            </button>
          </div>
        </div>
      `},ie=v.map(M=>{let C=String(M.map_id),j=this.escapeHtml(M.display_name??`Map ${C}`),V=t.isSetupMapConfigured?.(C),le=f===C||h===C,U=M.protection??null,ue=U?.requires_typed_confirmation??!1,ne=w===C,me=V&&!le?'<span class="evcc-setup-configured-badge">\u2713 Configured</span>':"",He=`
        <button class="evcc-setup-btn ${V?"secondary":""} small"
                data-action="setup-configure-map"
                data-map-id="${C}"
                ${c||x||S?"disabled":""}>
          ${le?"Close":V?"Reconfigure":"Configure Rooms"}
        </button>
      `,Ka=ne?"":`<button class="evcc-setup-btn destructive-ghost small"
                   data-action="setup-delete-map-open"
                   data-map-id="${C}"
                   data-requires-typed="${ue}"
                   ${c||x||S?"disabled":""}>
             Delete
           </button>`;return`
        <div class="evcc-setup-mapconfig-row">
          <div class="evcc-setup-mapconfig-header">
            <div class="evcc-setup-mapconfig-name">${j}</div>
            <div class="evcc-setup-mapconfig-actions">
              ${me}
              ${Ka}
              ${He}
            </div>
          </div>
          ${X(C,U)}
          ${se(C)}
        </div>
      `}).join(""),A=p,L=`
      <div class="evcc-setup-step">
        <div class="evcc-setup-step-header">
          <div class="evcc-setup-step-badge ${A?"done":""}">
            ${A?"\u2713":"2"}
          </div>
          <div class="evcc-setup-step-label">Import Maps &amp; Configure Rooms</div>
        </div>

        <div class="evcc-setup-step-body">
          ${m?"Configure each imported map \u2014 exclude ghost rooms and set floor types. Then import additional maps as needed.":"Import the vacuum's currently active map. Make sure it has completed a mapping run first."}
        </div>

        ${m?`<div class="evcc-setup-mapconfig-list">${ie}</div>`:""}

        ${u?`<button class="evcc-setup-btn ${m?"secondary":""}"
                     data-action="setup-import-map"
                     ${c?"disabled":""}>
               ${m?"Import Another Map":"Import Active Map"}
             </button>`:'<div class="evcc-setup-step-body muted">Complete step 1 first.</div>'}
      </div>
    `,z=p?`<div class="evcc-setup-result success">
           \u2713 Setup complete \u2014 switch to the Rooms tab to start cleaning.
         </div>`:m?`<div class="evcc-setup-result info">
           Configure rooms for each imported map to complete setup.
         </div>`:"",F=`
      <div class="evcc-setup-footer">
        <button class="evcc-setup-btn secondary"
                data-action="setup-refresh"
                ${c?"disabled":""}>
          ${n==null?"Check Status":"Refresh"}
        </button>
      </div>
    `;return`
      <div class="evcc-setup-view">

        <div class="evcc-setup-header">
          <div class="evcc-setup-title">Vacuum Setup</div>
          <div class="evcc-setup-description">
            Add your vacuum, import each of its maps, then configure rooms
            per map \u2014 this is where you exclude ghost rooms and set floor types.
          </div>
        </div>

        ${H}
        ${L}
        ${z}
        ${oe}
        ${ae}
        ${W}
        ${F}


      </div>
    `}}function jr(i){i.renderMappingReviewView=function(e){let{state:t}=e,r=t.mappingBoundsSnapshot?.();if(!r)return'<div class="evcc-empty">Loading mapping bounds...</div>';if(r.available===!1)return`
        <div class="evcc-mrev-view">
          <div class="evcc-empty">${this.escapeHtml(r.message||"Mapping bounds unavailable.")}</div>
        </div>`;let a=r.rooms??{},n=t.mappingBoundsFilter?.()??"all",c=t.mappingBoundsFilterOptions?.()??[],s=Object.keys(a),o=s.filter(m=>a[m]?.bounds),l=s.filter(m=>!a[m]?.bounds),d=s.reduce((m,p)=>m+(a[p]?.job_bounds_history?.length??0),0),v=[...s.filter(m=>n==="has_bounds"?!!a[m]?.bounds:n==="no_bounds"?!a[m]?.bounds:!0)].sort((m,p)=>{let f=!!a[m]?.bounds,h=!!a[p]?.bounds;return f!==h?f?-1:1:Number(m)-Number(p)});return`
      <div class="evcc-mrev-view">

        <section class="evcc-review-panel">
          <div class="evcc-review-panel-header">
            <div>
              <div class="evcc-review-panel-title">Mapping Bounds Review</div>
              <div class="evcc-review-panel-subtitle">
                Per-run bounds derived from job history. Exclude runs to remove outliers from accumulated bounds.
              </div>
            </div>
          </div>
          <div class="evcc-review-stats">
            ${this._renderReviewStat("Rooms",s.length)}
            ${this._renderReviewStat("With Bounds",o.length)}
            ${this._renderReviewStat("No Bounds",l.length)}
            ${this._renderReviewStat("Total Runs",d)}
          </div>
        </section>

        <section class="evcc-review-panel evcc-review-panel--wide">
          <div class="evcc-review-chip-filter">
            <div class="evcc-mrev-filter-label">Filter</div>
            <div class="evcc-chips evcc-review-filter-chips">
              ${c.map(m=>`
                <button class="evcc-chip ${n===m.value?"active":""}"
                        data-mrev-filter="${this.escapeHtml(m.value)}">
                  ${this.escapeHtml(m.label)}
                </button>
              `).join("")}
            </div>
          </div>
        </section>

        <div class="evcc-mrev-grid">
          ${v.map(m=>this._renderMappingRoomCard(m,a[m],t)).join("")}
        </div>

      </div>
    `},i._renderMappingRoomCard=function(e,t,r){let a=t?.name??`Room ${e}`,n=t?.bounds??null,c=t?.job_bounds_history??[],s=!!t?.has_archive,o=r.isMappingBoundsClearPending?.(e),l=r.isMappingRebuildPending?.(e),d=c.filter(f=>!f.excluded).length,u=c.filter(f=>f.excluded).length,m=d>=4,p=n?m?`<span class="evcc-mrev-badge evcc-mrev-badge--ok">${d} run${d!==1?"s":""} \xB7 ${n.sample_count??0} samples</span>`:`<span class="evcc-mrev-badge evcc-mrev-badge--likely">${d} run${d!==1?"s":""} \xB7 Likely</span>`:'<span class="evcc-mrev-badge evcc-mrev-badge--warn">No bounds</span>';return`
      <div class="evcc-mrev-card">
        <div class="evcc-mrev-card-header">
          <div class="evcc-mrev-room-name">${this.escapeHtml(a)}</div>
          <div class="evcc-mrev-room-meta">
            <span class="evcc-mrev-room-id">ID ${this.escapeHtml(e)}</span>
            ${p}
            ${u>0?`<span class="evcc-mrev-badge evcc-mrev-badge--excluded">${u} excluded</span>`:""}
          </div>
        </div>

        ${n?`<div class="evcc-mrev-bounds-block">
               ${this._renderBoundsTable(n)}
             </div>`:s?'<div class="evcc-mrev-no-bounds">No active bounds \u2014 archive available for rebuild.</div>':'<div class="evcc-mrev-no-bounds">Run solo to establish bounds.</div>'}

        ${c.length>0?`
          <div class="evcc-mrev-history">
            <div class="evcc-mrev-history-label">Run History (${c.length})</div>
            ${c.map((f,h)=>this._renderJobBoundsEntry(f,h,e,n,c,r)).join("")}
          </div>`:""}

        <div class="evcc-mrev-card-footer">
          ${!n&&s?`
            <button class="evcc-chip evcc-mrev-rebuild-btn ${l?"evcc-mrev-clear-btn--disabled":""}"
                    data-mrev-rebuild="${this.escapeHtml(e)}"
                    ${l?"disabled":""}>
              ${l?"Rebuilding\u2026":"Rebuild from Archive"}
            </button>`:""}
          <button class="evcc-chip evcc-mrev-clear-btn ${!n||o?"evcc-mrev-clear-btn--disabled":""}"
                  data-mrev-clear="${this.escapeHtml(e)}"
                  ${!n||o?"disabled":""}>
            ${o?"Clearing\u2026":"Clear All"}
          </button>
        </div>
      </div>
    `},i._renderBoundsTable=function(e){let t=Math.round(e.max_x-e.min_x),r=Math.round(e.max_y-e.min_y),a=n=>Math.round(n).toLocaleString();return`
      <div class="evcc-mrev-bounds-grid">
        <div class="evcc-mrev-bounds-row">
          <span class="evcc-mrev-bounds-key">X</span>
          <span class="evcc-mrev-bounds-val">${a(e.min_x)} \u2013 ${a(e.max_x)}</span>
          <span class="evcc-mrev-bounds-dim">w ${a(t)}</span>
        </div>
        <div class="evcc-mrev-bounds-row">
          <span class="evcc-mrev-bounds-key">Y</span>
          <span class="evcc-mrev-bounds-val">${a(e.min_y)} \u2013 ${a(e.max_y)}</span>
          <span class="evcc-mrev-bounds-dim">h ${a(r)}</span>
        </div>
        ${e.updated_at?`
        <div class="evcc-mrev-bounds-row evcc-mrev-bounds-row--sub">
          <span class="evcc-mrev-bounds-key">Updated</span>
          <span class="evcc-mrev-bounds-val">${this._mrevFmtDate(e.updated_at)}</span>
          <span class="evcc-mrev-bounds-dim"></span>
        </div>`:""}
      </div>
    `},i._renderJobBoundsEntry=function(e,t,r,a,n,c){let s=x=>Math.round(x).toLocaleString(),o=!!e.excluded,l=c.isMappingJobActionPending?.(r,t),d=[];if(!o){let x=n.filter((w,g)=>g!==t&&!w.excluded);if(x.length>0){let w={min_x:Math.min(...x.map(S=>S.min_x)),max_x:Math.max(...x.map(S=>S.max_x)),min_y:Math.min(...x.map(S=>S.min_y)),max_y:Math.max(...x.map(S=>S.max_y))},g=(w.max_x-w.min_x)*.1,R=(w.max_y-w.min_y)*.1;e.max_x>w.max_x+g&&d.push("max X"),e.min_x<w.min_x-g&&d.push("min X"),e.max_y>w.max_y+R&&d.push("max Y"),e.min_y<w.min_y-R&&d.push("min Y")}}let u=d.length>0,v=this._mrevFmtJobId(e.job_id),m=e.recorded_at?this._mrevFmtDate(e.recorded_at):"",p=t===n.length-1,f=n.filter(x=>!x.excluded).length,h=!o&&!l&&!p&&f>1,y=o&&!l&&!p;return`
      <div class="evcc-mrev-job-entry ${o?"evcc-mrev-job-entry--excluded":""} ${u?"evcc-mrev-job-entry--outlier":""}">
        <div class="evcc-mrev-job-header">
          <span class="evcc-mrev-job-id ${o?"evcc-mrev-job-id--excluded":""}">${this.escapeHtml(v)}</span>
          ${m?`<span class="evcc-mrev-job-date">${this.escapeHtml(m)}</span>`:""}
          ${o?'<span class="evcc-mrev-badge evcc-mrev-badge--excluded">Excluded</span>':u?`<span class="evcc-mrev-badge evcc-mrev-badge--outlier">Outlier: ${this.escapeHtml(d.join(", "))}</span>`:'<span class="evcc-mrev-badge evcc-mrev-badge--ok">OK</span>'}
          ${p?'<span class="evcc-mrev-badge evcc-mrev-badge--baseline">Baseline</span>':""}
          <div class="evcc-mrev-job-actions">
            ${h?`
              <button class="evcc-chip evcc-chip--sm evcc-mrev-job-action-btn"
                      data-mrev-job-action="exclude"
                      data-mrev-room-id="${this.escapeHtml(r)}"
                      data-mrev-job-index="${t}">
                Exclude
              </button>`:""}
            ${y?`
              <button class="evcc-chip evcc-chip--sm evcc-mrev-job-action-btn"
                      data-mrev-job-action="restore"
                      data-mrev-room-id="${this.escapeHtml(r)}"
                      data-mrev-job-index="${t}">
                Restore
              </button>`:""}
            ${l?'<span class="evcc-mrev-job-pending">\u2026</span>':""}
          </div>
        </div>
        <div class="evcc-mrev-bounds-grid evcc-mrev-bounds-grid--compact ${o?"evcc-mrev-bounds-grid--muted":""}">
          <div class="evcc-mrev-bounds-row">
            <span class="evcc-mrev-bounds-key">X</span>
            <span class="evcc-mrev-bounds-val">${s(e.min_x)} \u2013 ${s(e.max_x)}</span>
            <span class="evcc-mrev-bounds-dim">w ${s(e.max_x-e.min_x)}</span>
          </div>
          <div class="evcc-mrev-bounds-row">
            <span class="evcc-mrev-bounds-key">Y</span>
            <span class="evcc-mrev-bounds-val">${s(e.min_y)} \u2013 ${s(e.max_y)}</span>
            <span class="evcc-mrev-bounds-dim">h ${s(e.max_y-e.min_y)}</span>
          </div>
          <div class="evcc-mrev-bounds-row evcc-mrev-bounds-row--sub">
            <span class="evcc-mrev-bounds-key">Samples</span>
            <span class="evcc-mrev-bounds-val">${e.sample_count??"\u2014"}</span>
            <span class="evcc-mrev-bounds-dim"></span>
          </div>
        </div>
      </div>
    `},i._mrevFmtJobId=function(e){if(!e)return"Unknown";if(e==="pre_migration")return"Pre-migration";let t=String(e).match(/job_(\d{4}-\d{2}-\d{2})T(\d{2}-\d{2})/);return t?`${t[1]} ${t[2].replace("-",":")}`:String(e).slice(-16)},i._mrevFmtDate=function(e){if(!e)return"";try{return new Date(e).toLocaleString(void 0,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}catch{return String(e).slice(0,16)}}}function zr(i){i.renderIncompleteRunBanner=function(e){if(!e.hasIncompleteRunLog?.()||e.learningJobActive?.())return"";let t=e.incompleteRunLog(),r=e.incompleteRunMissedRooms(),a=r.length,n=String(t?.outcome_status??"cancelled").toLowerCase(),c={cancelled:"cancelled",failed:"failed",interrupted:"interrupted"}[n]??n,s=r.map(o=>`<span class="evcc-incomplete-run-room">${this.escapeHtml(o.name)}</span>`).join("");return`
      <div class="evcc-incomplete-run-banner" role="alert">
        <div class="evcc-incomplete-run-body">
          <div class="evcc-incomplete-run-title">
            Last run ${this.escapeHtml(c)} \u2014
            ${a} room${a===1?"":"s"} missed
          </div>
          <div class="evcc-incomplete-run-rooms">${s}</div>
        </div>
        <div class="evcc-incomplete-run-actions">
          <button
            class="evcc-incomplete-run-retry"
            data-action="queue-missed-rooms"
          >Queue missed rooms</button>
          <button
            class="evcc-incomplete-run-dismiss"
            data-action="dismiss-incomplete-run-log"
            aria-label="Dismiss"
          >\u2715</button>
        </div>
      </div>
    `},i.renderLearningPreJobPanel=function(e){let t=e.dashboardPlannedJobEstimate?.()??e.learningEstimate();if(!t)return"";if(t.error||t.available===!1)return`
        <div class="evcc-learning-panel evcc-learning-panel--empty">
          <div class="evcc-learning-panel-header">
            <div class="evcc-learning-panel-title">Estimate unavailable</div>
          </div>
          <div class="evcc-learning-empty-message">
            ${this.escapeHtml(t.error==="no_payload"?"Queue rooms first to see an estimate":t.message||t.error_detail||"Estimate unavailable.")}
          </div>
        </div>
      `;let r=this._formatLearningDuration(t.total_minutes),a=this._formatLearningWallClock(t.job_eta_at),n=t.confidence_breakpoint??null,c=this._formatLearningWallClock(t.stats_rebuilt_at),s=e.dashboardPlannedWaterEstimate?.(),o=e.dashboardStartStatus?.()??{},l=t.overhead??{},d=l.mop_wash??{},u=String(d.mode??"")==="by_time"&&Number(d.cycle_count??0)>0?`${this._formatLearningMinutes(l.mop_wash_minutes)} (${d.cycle_count} cycle${Number(d.cycle_count)===1?"":"s"} \xD7 ${this._formatLearningMinutes(d.minutes_per_cycle)} every ${this._formatLearningMinutes(d.interval_minutes)})`:"0 min (no cycles scheduled)";return`
      <div class="evcc-learning-panel evcc-learning-panel--prejob">
        <div class="evcc-learning-panel-header">
          <div class="evcc-learning-panel-title-group">
            <div class="evcc-learning-panel-title">Estimated Job Time</div>
            <div class="evcc-learning-panel-subtitle">
              ${this.escapeHtml(r)}
              ${a?` \xB7 done by ${this.escapeHtml(a)}`:""}
            </div>
          </div>

          ${this.renderConfidenceChip(n,this._learningConfidenceLabel(t.confidence_label,"job"))}
        </div>

        ${t.stats_stale?`
          <div class="evcc-learning-notice evcc-learning-notice--stale">
            \u26A0 Estimates may be outdated${c?` (last rebuilt ${this.escapeHtml(c)})`:""}
          </div>
        `:""}

        ${t.battery_warning?`
          <div class="evcc-learning-notice evcc-learning-notice--battery">
            \u26A1 May need to recharge mid-job
          </div>
        `:""}

        ${o?.water_warning_message&&Number(s?.mopping_room_count??0)>0?`
          <div class="evcc-learning-notice ${o?.water_warning_reason==="not_enough_clean_water"?"evcc-learning-notice--battery":"evcc-learning-notice--stale"}">
            ${this.escapeHtml(o.water_warning_message)}
          </div>
        `:""}

        ${this._renderLearningWaterEstimateChips(s)}

        ${s?.available&&Number(s.mopping_room_count??0)>0?`
          <div class="evcc-learning-water-summary">
            <div class="evcc-learning-panel-subtitle">Water estimate</div>

            <div class="evcc-learning-overhead-rows">
              <div class="evcc-learning-overhead-row">
                <span>Tank now</span>
                <span>
                  ${this.escapeHtml(this._formatLearningMilliliters(s.available_clean_tank_ml))}
                  ${Number.isFinite(Number(s.station_clean_water_percent))?` (${this.escapeHtml(`${Math.round(Number(s.station_clean_water_percent))}%`)})`:""}
                </span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>Job will use</span>
                <span>${this.escapeHtml(this._formatLearningMilliliters(s.estimated_total_dock_clean_water_used_ml))}</span>
              </div>

              <div class="evcc-learning-overhead-row">
                <span>Tank after run</span>
                <span>
                  ${this.escapeHtml(this._formatLearningMilliliters(s.estimated_clean_tank_remaining_ml))}
                  ${Number.isFinite(Number(s.estimated_clean_tank_remaining_percent))?` (${this.escapeHtml(`${Math.round(Number(s.estimated_clean_tank_remaining_percent))}%`)})`:""}
                </span>
              </div>
            </div>
          </div>
        `:""}

        <details class="evcc-learning-overhead">
          <summary class="evcc-learning-overhead-summary">Overhead breakdown</summary>

          <div class="evcc-learning-overhead-rows">
            <div class="evcc-learning-overhead-row">
              <span>Startup</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(l.startup_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Transitions</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(l.transition_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Recharge</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(l.recharge_minutes))}</span>
            </div>

            ${Number(d.cycle_count??0)>0?`
              <div class="evcc-learning-overhead-row">
                <span>Mop wash</span>
                <span>${this.escapeHtml(u)}</span>
              </div>
            `:""}

            <div class="evcc-learning-overhead-row">
              <span>Dust empty</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(l.dust_empty_minutes))}</span>
            </div>

            <div class="evcc-learning-overhead-row">
              <span>Return to dock</span>
              <span>${this.escapeHtml(this._formatLearningMinutes(l.return_minutes))}</span>
            </div>
          </div>
        </details>

      </div>
    `},i.renderLearningLiveBanner=function(e){if(!e.shouldShowLiveQueue())return"";let t=e.learningLiveBannerRoom(),r=e.learningAllCompleted?.()??!1,a=!!e.learningBatteryWarning?.(),n=r?"all-complete":String(t?.room_id??"pending");return`
      <div
        class="evcc-learning-live-banner evcc-learning-live-banner--animated"
        data-learning-key="${this.escapeHtml(n)}"
      >
        ${r?`
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">All rooms complete</div>
            <div class="evcc-learning-live-subtitle">Returning to dock</div>
          </div>
        `:t?`
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">
              \u25B6 Cleaning ${this.escapeHtml(t.room_name??"Next room")}
            </div>

            <div class="evcc-learning-live-subtitle">
              ${t.eta_at?`Done at ${this.escapeHtml(this._formatLearningWallClock(t.eta_at))}`:""}
            </div>
          </div>

          ${this.renderConfidenceChip(t.confidence_breakpoint??null,this._learningConfidenceLabel(t.confidence_label,"room"))}
        `:`
          <div class="evcc-learning-live-banner-main">
            <div class="evcc-learning-live-title">Learning active</div>
            <div class="evcc-learning-live-subtitle">Waiting for next room update</div>
          </div>
        `}
      </div>

      ${a?`
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          \u26A1 May need to recharge to finish remaining rooms
        </div>
      `:""}

      ${(()=>{let c=e.dashboardJobProgress?.();if(!c?.stall_detected)return"";let s=Number(c.stall_elapsed_minutes),o=Number(c.stall_expected_minutes),l=Number.isFinite(s)?this._formatLearningMinutes(s):null,d=Number.isFinite(o)?this._formatLearningMinutes(o):null,u=l&&d?` (${l} elapsed, expected ${d})`:l?` (${l} elapsed)`:"";return`
          <div class="evcc-learning-notice evcc-learning-notice--stall">
            \u23F3 Robot may be stuck in current room${this.escapeHtml(u)}
          </div>
        `})()}
    `},i.renderLearningProgressList=function(e){if(!e.shouldShowLiveQueue())return"";let t=e.learningRoomTimeline();return t.length?`
      <div class="evcc-learning-progress">
        <div class="evcc-learning-progress-title">Live Progress</div>

        <div class="evcc-learning-progress-list">
          ${t.map(r=>r.completed?this._renderLearningCompletedRow(r):r.current?this._renderLearningCurrentRow(r):!r.current&&!r.remaining&&!r.completed?this._renderLearningCurrentRow(r):this._renderLearningRemainingRow(r)).join("")}
        </div>
      </div>
    `:""},i.renderConfidenceChip=function(e,t,r=""){if(!e||!t)return"";let a=String(e.ui_variant??"").toLowerCase();return`
      <span class="evcc-learning-chip ${{success:"evcc-learning-chip--success",warning:"evcc-learning-chip--warning",error:"evcc-learning-chip--error"}[a]??"evcc-learning-chip--neutral"}" ${r?`title="${this.escapeHtml(r)}"`:""}>
        ${this.escapeHtml(t)}
      </span>
    `},i._renderLearningWaterEstimateChips=function(e){if(!e||e.available===!1)return"";let t=Array.isArray(e.rooms)?e.rooms:[],r=Number(e.estimated_total_dock_clean_water_used_ml),a=Number(e.wash_cycle_count??0),n=0,c=0,s=0;for(let l of t){let d=String(l.clean_mode??"").includes("vacuum"),u=!!l.mop_active;d&&u?s++:d?n++:u&&c++}if(n+c+s===0)return"";let o=[];return Number.isFinite(r)&&r>0&&o.push(`~${this._formatLearningMilliliters(r)} water`),n>0&&o.push(`${n} vacuum-only room${n===1?"":"s"}`),c>0&&o.push(`${c} mop-only room${c===1?"":"s"}`),s>0&&o.push(`${s} vacuum + mop room${s===1?"":"s"}`),a>0&&o.push(`${a} wash cycle${a===1?"":"s"}`),o.length?`
      <div class="evcc-learning-chip-row">
        ${o.map(l=>`
          <span class="evcc-learning-chip evcc-learning-chip--neutral">
            ${this.escapeHtml(l)}
          </span>
        `).join("")}
      </div>
    `:""},i._renderLearningPreJobRow=function(e){let t=[];return e.intensity_mismatch&&t.push("\u26A0 estimated from different intensity"),e.source==="default"&&t.push("No data yet"),Number(e?.learning_velocity?.runs_to_high??0)>0&&t.push(`${e.learning_velocity.runs_to_high} runs to reliable`),`
      <div
        class="evcc-learning-room-row evcc-learning-room-row--prejob"
        data-learning-key="${this.escapeHtml(String(e.room_id??e.position??""))}"
      >
        <div class="evcc-learning-room-main">
          <div class="evcc-learning-room-name">
            ${this.escapeHtml(e.room_name??`Room ${e.room_id??""}`)}
          </div>

          <div class="evcc-learning-room-meta">
            ${this.escapeHtml(this._formatLearningMinutes(e.minutes))}
            ${e.eta_at?` \xB7 ${this.escapeHtml(this._formatLearningWallClock(e.eta_at))}`:""}
          </div>

          ${t.length?`
            <div class="evcc-learning-room-notes">
              ${t.map(r=>`<div class="evcc-learning-room-note">${this.escapeHtml(r)}</div>`).join("")}
            </div>
          `:""}
        </div>

        ${this.renderConfidenceChip(e.confidence_breakpoint??null,this._learningConfidenceLabel(e.confidence_label,"room"))}
      </div>
    `},i._renderLearningCompletedRow=function(e){return`
      <div
        class="evcc-learning-progress-row evcc-learning-progress-row--completed evcc-learning-progress-row--animated"
        data-learning-key="${this.escapeHtml(String(e.room_id??e.position??""))}"
      >
        <div class="evcc-learning-progress-main">
          <div class="evcc-learning-progress-name">
            \u2713 ${this.escapeHtml(e.room_name??`Room ${e.room_id??""}`)}
          </div>
          <div class="evcc-learning-progress-meta">
            ${this.escapeHtml(this._formatLearningMinutes(e.actual_duration_minutes))}
          </div>
        </div>
      </div>
    `},i._renderLearningCurrentRow=function(e){let t=this.card?._learningController?.getRoomProgressSnapshot?.(e.room_id)??null,r=t?.isCurrent?`${t.percent}%${Number.isFinite(t.remainingMinutes)?` \xB7 ~${this._formatLearningMinutes(t.remainingMinutes)} left`:""}`:e.eta_at?`Done at ${this.escapeHtml(this._formatLearningWallClock(e.eta_at))}`:"";return`
    <div
      class="evcc-learning-progress-row evcc-learning-progress-row--current evcc-learning-progress-row--animated"
      data-learning-key="${this.escapeHtml(String(e.room_id??e.position??""))}"
    >
      <div class="evcc-learning-progress-main">
        <div class="evcc-learning-progress-name">
          \u25B6 ${this.escapeHtml(e.room_name??`Room ${e.room_id??""}`)}
        </div>
        <div class="evcc-learning-progress-meta">
          ${this.escapeHtml(r)}
        </div>
      </div>

      <div class="evcc-learning-progress-side">
        <div class="evcc-learning-progress-minutes">
          ${this.escapeHtml(this._formatLearningMinutes(e.minutes))}
        </div>
        ${this.renderConfidenceChip(e.confidence_breakpoint??null,this._learningConfidenceLabel(e.confidence_label,"room"))}
      </div>
    </div>
  `},i._renderLearningRemainingRow=function(e){return`
      <div
        class="evcc-learning-progress-row evcc-learning-progress-row--remaining evcc-learning-progress-row--animated"
        data-learning-key="${this.escapeHtml(String(e.room_id??e.position??""))}"
      >
        <div class="evcc-learning-progress-main">
          <div class="evcc-learning-progress-name">
            \u25CB ${this.escapeHtml(e.room_name??`Room ${e.room_id??""}`)}
          </div>
          <div class="evcc-learning-progress-meta">
            ${e.eta_at?this.escapeHtml(this._formatLearningWallClock(e.eta_at)):""}
          </div>
        </div>
      </div>
    `},i._formatLearningMinutes=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:"0 min"},i._formatLearningDuration=function(e){let t=Number(e);if(!Number.isFinite(t))return"0 min";let r=Math.round(t),a=Math.floor(r/60),n=r%60;return a<=0?`${n} min`:n<=0?`${a}h`:`${a}h ${n}m`},i._formatLearningMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"Unknown"},i._formatLearningWallClock=function(e){return this.formatTimestamp(e,{hour:"numeric",minute:"2-digit"},"")},i._learningConfidenceLabel=function(e,t="room"){let r=String(e??"").trim().toLowerCase();if(!r)return"";let a=r.charAt(0).toUpperCase()+r.slice(1);return t==="job"?`${a} confidence`:a},i.renderLearningSummary=function(e){if(!e.hasLearningSummary())return"";let t=e.learningSummary(),r=this._formatLearningDuration(t.total_minutes),a=this._formatLearningWallClock(t.finished_at),n=Number(t.predicted_total_minutes??t.predicted_minutes),c=Number.isFinite(n),s=c?Number(t.total_minutes)-n:null,o=Number.isFinite(s)?`${s>0?"+":""}${this._formatLearningDuration(Math.abs(s))}`:"";return`
    <div class="evcc-learning-panel evcc-learning-panel--summary">

      <div class="evcc-learning-panel-header">
        <div class="evcc-learning-panel-title-group">
          <div class="evcc-learning-panel-title">Cleaning Complete</div>
          <div class="evcc-learning-panel-subtitle">
            ${a?`Finished at ${this.escapeHtml(a)}`:""}
          </div>
        </div>

        <button
          class="evcc-chip evcc-learning-chip--neutral"
          data-action="dismiss-learning-summary"
        >
          Dismiss
        </button>
      </div>

      <div class="evcc-learning-summary-stats">

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(r)}</div>
          <div class="evcc-learning-summary-label">Actual</div>
        </div>

        <div class="evcc-learning-summary-stat">
          <div class="evcc-learning-summary-value">${this.escapeHtml(t.rooms_completed)}</div>
          <div class="evcc-learning-summary-label">Rooms</div>
        </div>

        ${c?`
          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(this._formatLearningDuration(n))}</div>
            <div class="evcc-learning-summary-label">Predicted</div>
          </div>

          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(o)}</div>
            <div class="evcc-learning-summary-label">Delta</div>
          </div>
        `:""}

      </div>

      ${t.battery_warning?`
        <div class="evcc-learning-notice evcc-learning-notice--battery">
          \u26A1 Recharge occurred during job
        </div>
      `:""}

    </div>
  `}}var B=class{constructor(e){this.card=e}sync(e){return this.card=e,this}};yr(B.prototype);xr(B.prototype);wr(B.prototype);Sr(B.prototype);Rr(B.prototype);Er(B.prototype);kr(B.prototype);Tr(B.prototype);$r(B.prototype);Mr(B.prototype);Ir(B.prototype);Ar(B.prototype);Pr(B.prototype);Nr(B.prototype);Hr(B.prototype);Dr(B.prototype);zr(B.prototype);Br(B.prototype);jr(B.prototype);function Vr(i){i._bindNav=function(){this.card._onAll("[data-view]","click",e=>{let t=e.currentTarget.dataset.view;t&&this.card.setView(t)})}}function qr(i){i._bindBaseStation=function(){this.card._onAll("[data-pause-timeout-minutes]","click",async e=>{let t=e.currentTarget?.dataset?.pauseTimeoutMinutes,r=Number(t);if(!(!Number.isFinite(r)||!this.card._actions))try{let a=await this.card._actions.setPauseTimeoutSettings?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),pause_timeout_minutes_default:r});a&&this.card._state.setPauseTimeoutSettings?.(a),this.card._scheduleRender()}catch(a){console.error("[eufy-vacuum-command-center] Failed to set pause timeout:",a)}}),this.card._onAll("[data-dock-action]","click",async e=>{let t=e.currentTarget?.dataset?.dockAction;if(!t||!this.card._actions)return;let a={wash_mop:"washMop",dry_mop:"dryMop",stop_dry_mop:"stopDryMop",empty_dust:"emptyDust"}[t];if(!(!a||typeof this.card._actions[a]!="function")){this.card._state.beginDockAction?.(t),this.card._scheduleRender();try{await this.card._actions[a]()}finally{this.card._state.endDockAction?.(),await this.card.refreshDashboardSnapshot?.(),await this.card.refreshDockActionStatus?.(),this.card._scheduleRender()}}})}}function Gr(i){i._bindMaintenance=function(){this.card._onAll("[data-maintenance-tab]","click",e=>{let t=e.currentTarget?.dataset?.maintenanceTab;t&&(this.card._state.setMaintenanceActiveTab?.(t),this.card._scheduleRender())}),this.card._onAll("[data-action='open-maintenance-modal']","click",e=>{let t=e.currentTarget,r=t?.dataset?.itemKind,a=t?.dataset?.itemComponent,n=t?.dataset?.itemEntityId;if(!r||!a)return;let c=this.card._state.findUpkeepItem?.(r,a,n);c&&(this.card._state.openMaintenanceModal?.(c),this.card._scheduleRender())})},i._bindMaintenanceModalHost=function(e){e&&(e.querySelectorAll("[data-action='close-maintenance-modal']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.closeMaintenanceModal?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='begin-maintenance-reset']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.beginMaintenanceResetConfirmation?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='cancel-maintenance-reset']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.cancelMaintenanceResetConfirmation?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='confirm-maintenance-reset']").forEach(t=>{t.addEventListener("click",async()=>{let r=this.card._state.activeMaintenanceModalItem?.();if(!r||!this.card._state.canInvokeMaintenanceReset?.(r))return;if(this.card._state.setMaintenanceResetPending?.(!0),this.card._scheduleRender(),await this.card._actions.callNamedService?.(r.reset_service,r.reset_service_data)===null){this.card._state.setMaintenanceResetError?.(`Could not reset ${r.label??r.component??"item"}`),this.card._scheduleRender();return}await this.card.refreshDashboardSnapshot?.();let n=String(r?.reset_kind??"").trim().toLowerCase()==="integration"?"Maintenance reset saved":"Replacement reset sent",c=this.card._state.findUpkeepItem?.(r.kind,r.component,r.entity_id);c&&this.card._state.openMaintenanceModal?.(c),this.card._state.setMaintenanceResetSuccess?.(n),this.card._scheduleRender()})}))}}function Ur(i){i._bindMetrics=function(){this.card._onAll("[data-metrics-save-profile]","click",async e=>{let t=e.currentTarget?.dataset?.metricsSaveProfile,r=e.currentTarget?.dataset?.profileKey,a=e.currentTarget?.dataset?.roomSlug;if(!t||!r)return;let n=this.card._state.findMetricsSaveCandidate?.(t,r,a),c=String(n?.save_service??"").trim(),s=n?.save_service_data;if(!n||n?.save_supported===!1||!c||!s)return;let o=this.card._state.metricsProfileSaveKey?.(t,n);this.card._state.beginMetricsProfileSave?.(o),this.card._scheduleRender();try{await this.card._actions.callNamedService?.(c,s,!0),await this.card.refreshMetricsSnapshot?.(),await this.card.refreshLearningHistorySnapshot?.()}finally{this.card._state.endMetricsProfileSave?.(),this.card._scheduleRender()}}),this.card._onAll("[data-metrics-filter-chip]","click",async e=>{let t=e.currentTarget?.dataset?.metricsFilterChip,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setMetricsFilter?.(t,r),await this.card.refreshMetricsSnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-metrics-filter]","change",async e=>{let t=e.currentTarget?.dataset?.metricsFilter,r=e.currentTarget?.value;t&&(this.card._state.setMetricsFilter?.(t,r),await this.card.refreshMetricsSnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-metrics-tab]","click",e=>{let t=e.currentTarget?.dataset?.metricsTab;t&&(this.card._state.setMetricsActiveTab?.(t),this.card._scheduleRender())})}}function Wr(i){i._orderRoot=function(){return this.card?.shadowRoot??null},i._captureOrderedRects=function(e){let t=this._orderRoot();if(!t)return new Map;let r=t.querySelectorAll(`[data-order-drop-target][data-scope="${e}"]`),a=new Map;return r.forEach(n=>{let c=n.dataset.itemId;c&&a.set(String(c),{left:n.getBoundingClientRect().left,top:n.getBoundingClientRect().top})}),a},i._applyOrderFeedback=function(e,t){let r=this._orderRoot();if(!r||t==null)return;let a=`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(t)}"]`,n=r.querySelector(a);n&&(n.classList.remove("evcc-order-feedback"),n.offsetWidth,n.classList.add("evcc-order-feedback"),window.setTimeout(()=>{n.classList.remove("evcc-order-feedback")},900))},i._playOrderFlip=function(e,t){let r=this._orderRoot();if(!r||!t?.size)return;r.querySelectorAll(`[data-order-drop-target][data-scope="${e}"]`).forEach(n=>{let c=String(n.dataset.itemId??"");if(!c||!t.has(c))return;let s=t.get(c),o=n.getBoundingClientRect(),l=s.left-o.left,d=s.top-o.top;Math.abs(l)<1&&Math.abs(d)<1||n.animate([{transform:`translate(${l}px, ${d}px)`},{transform:"translate(0px, 0px)"}],{duration:240,easing:"cubic-bezier(0.22, 1, 0.36, 1)"})})},i._runOrderMutationWithFlip=async function(e,t,r){let a=this._captureOrderedRects(e);await r()&&(this.card._scheduleRender(),await new Promise(c=>requestAnimationFrame(c)),await new Promise(c=>requestAnimationFrame(c)),this._playOrderFlip(e,a),this._applyOrderFeedback(e,t))},i.confirmOrderSelectorWithFlip=async function(){let e=this.card._state.orderSelectorScope(),t=this.card._state.orderSelectorItemId();await this._runOrderMutationWithFlip(e,t,async()=>await this.card._actions.confirmOrderedPositionChange())},i.confirmDraggedOrderWithFlip=async function(e,t){let r=this.card._state.orderDragItemId();await this._runOrderMutationWithFlip(e,r,async()=>await this.card._actions.confirmDraggedOrderChange(e,t))},i._clearDragVisualState=function(){let e=this._orderRoot();e&&(e.querySelectorAll(".evcc-order-drag-source").forEach(t=>{t.classList.remove("evcc-order-drag-source")}),e.querySelectorAll(".evcc-order-drag-target").forEach(t=>{t.classList.remove("evcc-order-drag-target")}))},i._applyDragVisualState=function(e,t,r){let a=this._orderRoot();if(a){if(this._clearDragVisualState(),t!=null){let n=a.querySelector(`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(t)}"]`);n&&n.classList.add("evcc-order-drag-source")}if(r!=null){let n=a.querySelector(`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(r)}"]`);n&&n.classList.add("evcc-order-drag-target")}}},i.bindOrderEvents=function(e){e&&(e.addEventListener("click",t=>{let r=t.target.closest("[data-action]");if(!r)return;let a=r.dataset.action;a==="open-order-selector"&&(t.preventDefault(),t.stopPropagation(),this.card._state.openOrderSelector(r.dataset.scope,r.dataset.itemId),this.card._scheduleRender()),a==="close-order-selector"&&(t.preventDefault(),this.card._state.closeOrderSelector(),this.card._scheduleRender()),a==="set-order-position"&&(t.preventDefault(),this.card._state.setOrderSelectorTargetPosition(r.dataset.position),this.card._scheduleRender()),a==="confirm-order-selector"&&(t.preventDefault(),this.confirmOrderSelectorWithFlip())}),e.addEventListener("dragstart",t=>{let r=t.target.closest("[data-order-drag-item]");if(!r)return;let a=r.dataset.scope,n=r.dataset.itemId;if(!(!a||n==null)){this.card._state.beginOrderDrag(a,n);try{t.dataTransfer.effectAllowed="move",t.dataTransfer.setData("text/plain",String(n))}catch{}this._applyDragVisualState(a,n,n)}}),e.addEventListener("dragover",t=>{let r=t.target.closest("[data-order-drop-target]");if(!r)return;t.preventDefault();let a=r.dataset.scope,n=r.dataset.itemId;!a||n==null||(this.card._state.setOrderDragOverItem(n),this._applyDragVisualState(a,this.card._state.orderDragItemId(),n))}),e.addEventListener("drop",t=>{let r=t.target.closest("[data-order-drop-target]");if(!r)return;t.preventDefault();let a=r.dataset.scope,n=r.dataset.itemId;this._clearDragVisualState(),this.confirmDraggedOrderWithFlip(a,n)}),e.addEventListener("dragend",()=>{this.card._state.clearOrderDrag(),this._clearDragVisualState()}))}}function Jr(i){i._bindRunProfiles=function(){this.card._on(this.card.$("[data-action='open-new-run-profile']"),"click",()=>{this.card._state.openNewRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='cancel-run-profile-editor']"),"click",()=>{this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._onAll("[data-run-profile-field='name']","input",e=>{this.card._state.updateRunProfileDraft?.("name",e.currentTarget.value)}),this.card._onAll("[data-run-profile-field='expose_as_button']","change",e=>{this.card._state.updateRunProfileDraft?.("expose_as_button",e.currentTarget.checked),this.card._scheduleRender()}),this.card._onAll("[data-action='apply-run-profile']","click",async e=>{let t=e.currentTarget.dataset.profileId;if(!t)return;this.card._state.selectRunProfile?.(t);let r=await this.card._actions.applyRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:t});if(r?.ok===!1){alert(r.reason||"Unable to apply run profile.");return}this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),this.card._state.closeRunProfileEditor?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='save-new-run-profile']"),"click",async()=>{let e=this.card._state.runProfileDraft?.(),t=String(e?.name??"").trim();if(!t){alert("Enter a name for the run profile.");return}let r=await this.card._actions.saveRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),name:t,expose_as_button:!!e?.expose_as_button});if(r?.ok===!1){alert(r.reason||"Unable to save run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(r?.profile_id??null),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='edit-run-profile']"),"click",e=>{let t=e.currentTarget.dataset.profileId;t&&(this.card._state.selectRunProfile?.(t),this.card._state.openSelectedRunProfileEditor?.(),this.card._scheduleRender())}),this.card._on(this.card.$("[data-action='overwrite-run-profile']"),"click",async()=>{let e=this.card._state.selectedRunProfile?.(),t=this.card._state.runProfileDraft?.();if(!e)return;let r=String(t?.name??"").trim();if(!r){alert("Enter a name for the run profile.");return}let a=await this.card._actions.overwriteRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:e.id,name:r,expose_as_button:!!t?.expose_as_button});if(a?.ok===!1){alert(a.reason||"Unable to overwrite run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(e.id),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='delete-run-profile']"),"click",async e=>{let t=e.currentTarget.dataset.profileId,r=this.card._state.selectedRunProfile?.();if(!t||!r||!confirm(`Delete run profile "${r.name}"?`))return;let a=await this.card._actions.deleteRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:t});if(a?.ok===!1){alert(a.reason||"Unable to delete run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(null),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()})}}function Kr(i){i._bindReview=function(){this.card._onAll("[data-review-filter-chip]","click",async e=>{let t=e.currentTarget?.dataset?.reviewFilterChip,r=e.currentTarget?.dataset?.value;if(t){if(t==="sort"){this.card._state.setLearningHistorySort?.(r),this.card._scheduleRender();return}this.card._state.setLearningHistoryFilter?.(t,r),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender()}}),this.card._onAll("[data-review-matcher-field]","click",e=>{let t=e.currentTarget?.dataset?.reviewMatcherField,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setReviewProfileMatcherField?.(t,r),this.card._scheduleRender())}),this.card._onAll("[data-review-matcher-action]","click",e=>{e.currentTarget?.dataset?.reviewMatcherAction==="reset"&&(this.card._state.resetReviewProfileMatcher?.(),this.card._scheduleRender())}),this.card._onAll("[data-review-matcher-profile]","click",async e=>{let t=e.currentTarget?.dataset?.reviewMatcherProfile;t&&(this.card._state.setLearningHistoryFilter?.("profile_key",t),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-review-filter]","change",async e=>{let t=e.currentTarget?.dataset?.reviewFilter,r=e.currentTarget?.value;if(t){if(t==="sort"){this.card._state.setLearningHistorySort?.(r),this.card._scheduleRender();return}this.card._state.setLearningHistoryFilter?.(t,r),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender()}}),this.card._onAll("[data-review-reason-chip]","click",e=>{let t=e.currentTarget?.dataset?.reviewReasonChip,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setLearningHistoryExcludeReason?.(t,r),this.card._scheduleRender())}),this.card._onAll("[data-review-action]","click",async e=>{let t=e.currentTarget?.dataset?.reviewAction,r=e.currentTarget?.dataset?.jobId;if(!(!t||!r)){this.card._state.beginLearningHistoryJobAction?.(r),this.card._scheduleRender();try{t==="exclude"&&await this.card._actions.excludeLearningJob?.({job_id:r,reason:this.card._state.learningHistoryExcludeReason?.(r)}),t==="restore"&&await this.card._actions.restoreLearningJob?.({job_id:r}),await this.card.refreshLearningHistorySnapshot?.()}finally{this.card._state.endLearningHistoryJobAction?.(),this.card._scheduleRender()}}})}}function Yr(i){i._bindRooms=function(){this._bindRoomToggles(),this._bindRoomActions(),this._bindQueueChipActions()},i._bindRoomToggles=function(){this.card._onAll("[data-room-card-toggle='true']","click",async e=>{if(e.target.closest("[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"))return;let t=e.currentTarget,r=Number(t.dataset.roomId),a=String(t.dataset.mapId),n=t.dataset.enabled==="true";!r||!a||(await this.card._actions.toggleRoomEnabled(a,r,n),n?this.card._state.disableSegmentForRoom?.(r):this.card._state.enableSegmentForRoom?.(r),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card.refreshDashboardSnapshot?.())}),this.card._onAll("[data-room-card-toggle='true']","keydown",async e=>{if(e.key!=="Enter"&&e.key!==" "||e.target.closest("[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"))return;e.preventDefault();let t=e.currentTarget,r=Number(t.dataset.roomId),a=String(t.dataset.mapId),n=t.dataset.enabled==="true";!r||!a||(await this.card._actions.toggleRoomEnabled(a,r,n),n?this.card._state.disableSegmentForRoom?.(r):this.card._state.enableSegmentForRoom?.(r),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card.refreshDashboardSnapshot?.())})},i._bindRoomActions=function(){this.card._on(this.card.$("[data-action='primary-room-action']:not([disabled])"),"click",async()=>{if(this.card._state.cancelRunRequiresConfirmation?.()){await this.card._actions.cancelActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender();return}if(this.card._state.hasActiveRun?.()){this.card._state.requestCancelRunConfirmation?.(),this.card._scheduleRender();return}if(this.card._state.startRequiresConfirmation?.()){await this.card._actions.startCleaning({confirmReducedRun:!0,confirmToken:this.card._state.startConfirmationToken?.()}),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender();return}await this.card._actions.startCleaning(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='cancel-primary-confirmation']"),"click",()=>{this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='pause-run']"),"click",async()=>{await this.card._actions.pauseActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='resume-run']"),"click",async()=>{await this.card._actions.resumeActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='locate-vacuum']"),"click",async()=>{await this.card._actions.locateVacuum(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='select-all']"),"click",async()=>{this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card._actions.selectAllRooms(),await this.card.refreshDashboardSnapshot?.()}),this.card._on(this.card.$("[data-action='clear-queue']"),"click",async()=>{this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card._actions.clearQueue(),await this.card.refreshDashboardSnapshot?.()}),this.card._on(this.card.$("[data-action='dismiss-learning-summary']"),"click",()=>{this.card._learningController.dismissLearningSummary()}),this.card._on(this.card.$("[data-action='dismiss-incomplete-run-log']"),"click",()=>{this.card._state.clearIncompleteRunLog?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='queue-missed-rooms']"),"click",async()=>{let e=this.card._state.incompleteRunMissedRoomIds?.()??[];this.card._state.clearIncompleteRunLog?.(),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),e.length>0&&(await this.card._actions.retryMissedRooms(e),await this.card.refreshDashboardSnapshot?.()),this.card._scheduleRender()})},i._bindQueueChipActions=function(){let e=Array.from(this.card.shadowRoot?.querySelectorAll("[data-queue-chip='true']")??[]),t=this.card._state.queueChipLongPressMs(),r=280;e.forEach(a=>{let n=null,c=!1,s=!1,o=null;a.title="Click for settings - Double-click for estimate - Hold to remove from queue";let l=()=>{o&&(window.clearTimeout(o),o=null)},d=()=>{n&&(window.clearTimeout(n),n=null),s=!1},u=m=>{m.button!=null&&m.button!==0||(c=!1,s=!0,a.classList.add("is-pressing"),n=window.setTimeout(async()=>{if(!s)return;c=!0,l(),a.classList.remove("is-pressing"),a.classList.add("is-long-pressing");let p=Number(a.dataset.roomId),f=String(a.dataset.mapId),h=a.dataset.enabled==="true";try{await this.card._actions.toggleRoomEnabled(f,p,h),await this.card.refreshDashboardSnapshot?.()}finally{a.classList.remove("is-long-pressing")}},t))},v=()=>{a.classList.remove("is-pressing"),d()};a.addEventListener("pointerdown",u),a.addEventListener("pointerup",()=>{a.classList.remove("is-pressing"),d()}),a.addEventListener("pointerleave",v),a.addEventListener("pointercancel",v),a.addEventListener("click",m=>{if(c){m.preventDefault(),m.stopPropagation(),c=!1,l();return}let p=Number(a.dataset.roomId),f=String(a.dataset.mapId);!p||!f||(l(),o=window.setTimeout(()=>{this.card._state.openRoomEditor(p,f),this.card._scheduleRender(),o=null},r))}),a.addEventListener("dblclick",m=>{if(m.preventDefault(),m.stopPropagation(),c){c=!1,l();return}l();let p=Number(a.dataset.roomId),f=String(a.dataset.mapId);!p||!f||(this.card._state.openRoomEstimateModal?.(p,f),this.card._scheduleRender())}),a.addEventListener("contextmenu",m=>{m.preventDefault()})})}}function Qr(i){i._bindRoomAccess=function(){},i._bindRoomAccessHost=function(e){if(!e)return;e.querySelectorAll("[data-action='open-room-access']").forEach(r=>{r.addEventListener("click",a=>{a.stopPropagation();let n=r.dataset.roomId,c=r.dataset.mapId;!n||!c||(this.card._state.closeRoomEditor?.(),this.card._state.openRoomAccess?.(n,c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='close-room-access']").forEach(r=>{r.addEventListener("click",()=>{this.card._state.closeRoomAccess?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='toggle-is-dock-room']").forEach(r=>{r.addEventListener("click",a=>{a.stopPropagation(),this.card._state.toggleIsDockRoomField?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='toggle-room-access-target']").forEach(r=>{r.addEventListener("click",a=>{a.stopPropagation();let n=r.dataset.roomId;n&&(this.card._state.toggleRoomAccessTarget?.(n),this.card._scheduleRender())})});let t=e.querySelector("[data-action='save-room-access']");t&&t.addEventListener("click",async()=>{let r=this.card._state.activeAccessRoom?.(),a=this.card._state.roomAccessFields?.(),n=this.card._state.roomAccessValidation?.();if(!(!r||!a||!n?.valid))try{let c=await this.card._actions.saveRoomAccess?.(r.id,a.grants_access_to??[],a.is_dock_room??!1);if(c?.ok===!1||c?.updated===!1||c?.error==="invalid_access_graph"||c?.reason==="invalid_access_graph"){let s=(Array.isArray(c?.issues)&&c.issues.length?c.issues.map(o=>o?.message??String(o)).join(" "):null)??c?.reason_detail??c?.message??c?.reason??"The backend rejected this room access graph.";this.card._state.setRoomAccessSaveError?.(s),this.card._scheduleRender();return}this.card._state.closeRoomAccess?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(c){console.error("[eufy-vacuum-command-center] Failed to save room access:",c),this.card._state.setRoomAccessSaveError?.("Failed to save room access. Check Home Assistant logs for details."),this.card._scheduleRender()}})}}function Xr(i){i._bindRoomEstimate=function(){},i._bindRoomEstimateHost=function(e){e&&e.querySelectorAll("[data-action='close-room-estimate']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.closeRoomEstimateModal?.(),this.card._scheduleRender()})})}}function Zr(i){i._bindRoomEditor=function(){this._bindRoomEditorOpen(),this._bindRoomEditorClose(),this._bindRoomEditorFields(),this._bindRoomEditorSave(),this._bindRoomEditorTransition()},i._refreshRoomEditorEstimates=async function(){try{await this.card._learningController?.loadRoomEstimates?.(),await this.card.refreshDashboardSnapshot?.()}catch(e){console.error("[eufy-vacuum-command-center] Failed to refresh room estimates:",e)}},i._refreshRoomProfileLibrary=async function(){try{await this.card.refreshRoomProfiles?.()}catch(e){console.error("[eufy-vacuum-command-center] Failed to refresh room profile library:",e)}},i._roomProfileTargetChoices=function(){return(this.card._state.customRoomProfiles?.()??[]).map(e=>`${e.name} (${e.label})`).join(`
`)},i._resolveEditableRoomProfileTarget=function(){let e=this.card._state.currentEditorManagedProfileName?.();if(e&&!this.card._state.isProtectedRoomProfile?.(e))return e;let t=this.card._state.customRoomProfiles?.()??[];if(!t.length)return null;let r=this._roomProfileTargetChoices(),a=window.prompt(`Choose a custom profile key:

${r}`,t[0]?.name??""),n=String(a??"").trim();if(!n)return null;let c=t.find(o=>o.name===n);return c?c.name:t.find(o=>String(o.label).toLowerCase()===n.toLowerCase())?.name??null},i._alertRoomProfileResult=function(e,t){let r=String(e?.message??e?.reason??t??"").trim();r&&window.alert(r)},i._defaultRoomProfileLabel=function(){let e=this.card._state.currentEditorManagedProfileName?.(),t=e?this.card._state.roomProfileDefinition?.(e):null,r=this.card._state.activeEditorRoom?.();return t?.label??r?.name??"Custom Room Profile"},i._openRoomEditorWithProfiles=async function(e,t){this.card._state.openRoomEditor(e,t),this.card._scheduleRender(),await this._refreshRoomProfileLibrary()},i._handleSaveRoomProfileAsNew=async function(){let e=this.card._state.activeEditorRoom?.();if(!e)return;let t=window.prompt("Save current room settings as a new profile. Enter a display label:",this._defaultRoomProfileLabel()),r=String(t??"").trim();if(!r)return;let a=this.card._state.makeRoomProfileName?.(r),n=await this.card._actions.saveRoomProfileFromRoom?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:String(e.mapId),room_id:e.id,label:r,profile_name:a});if(!n?.saved){this._alertRoomProfileResult(n,"Failed to save room profile.");return}await this._refreshRoomProfileLibrary();let c=String(n?.profile_name??a??"").trim();c&&this.card._state.applyEditorProfile?.(c),this.card._scheduleRender()},i._handleOverwriteRoomProfile=async function(){let e=this.card._state.activeEditorRoom?.();if(!e)return;let t=this._resolveEditableRoomProfileTarget();if(!t)return;let r=this.card._state.roomProfileDefinition?.(t);if(!window.confirm(`Overwrite ${r?.label??t} with this room's current settings?`))return;let n=await this.card._actions.overwriteRoomProfileFromRoom?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:String(e.mapId),room_id:e.id,profile_name:t});if(!n?.overwritten){this._alertRoomProfileResult(n,"Failed to overwrite room profile.");return}await this._refreshRoomProfileLibrary(),this.card._state.applyEditorProfile?.(t),this.card._scheduleRender()},i._handleRenameRoomProfile=async function(){let e=this._resolveEditableRoomProfileTarget();if(!e)return;let t=this.card._state.roomProfileDefinition?.(e);if(!t||this.card._state.isProtectedRoomProfile?.(e))return;let r=window.prompt("Enter the new display label for this room profile:",t.label);if(r==null)return;let a=String(r).trim();if(!a){window.alert("A room profile label is required.");return}let n=this.card._state.makeRoomProfileName?.(a,e),c=window.prompt("Optional: enter a new backend profile key.",n??e);if(c==null)return;let s=String(c).trim(),o=await this.card._actions.renameRoomProfile?.({profile_name:e,new_profile_name:s&&s!==e?s:void 0,label:a!==t.label?a:void 0});if(!o?.renamed){this._alertRoomProfileResult(o,"Failed to rename room profile.");return}await this._refreshRoomProfileLibrary();let l=this.card._state.currentEditorManagedProfileName?.(),d=String(o?.profile_name??o?.target_profile_name??e).trim();l===e&&d&&this.card._state.applyEditorProfile?.(d),this.card._scheduleRender()},i._handleDeleteRoomProfile=async function(){let e=this._resolveEditableRoomProfileTarget();if(!e)return;let t=this.card._state.roomProfileDefinition?.(e);if(!t||this.card._state.isProtectedRoomProfile?.(e)||!window.confirm(`Delete ${t.label}? This cannot be undone.`))return;let a=await this.card._actions.deleteRoomProfile?.({profile_name:e});if(!a?.deleted){this._alertRoomProfileResult(a,"Failed to delete room profile.");return}await this._refreshRoomProfileLibrary(),this.card._state._syncEditorProfileFromFields?.(),this.card._scheduleRender()},i._bindRoomEditorOpen=function(){this.card._onAll("[data-action='open-room-settings']","click",async e=>{e.stopPropagation();let t=e.currentTarget,r=t.dataset.roomId,a=t.dataset.mapId;!r||!a||await this._openRoomEditorWithProfiles(r,a)})},i._bindRoomEditorClose=function(){let e=this.card.$("[data-stop-propagation]");e&&e.addEventListener("click",t=>t.stopPropagation()),this.card._onAll("[data-action='close-room-editor']","click",async()=>{this.card._state.shouldSkipRefreshOnClose()?this.card._state.setSkipRefreshOnClose(!1):await this._refreshRoomEditorEstimates(),this.card._state.closeRoomEditor(),this.card._scheduleRender()})},i._bindRoomEditorFields=function(){this.card._onAll("[data-field]","click",e=>{let t=e.currentTarget,r=t.dataset.field,a=t.dataset.value;if(!(!r||a===void 0)){if(t.dataset.action==="apply-profile"){this.card._state.applyEditorProfile(a),this.card._scheduleRender();return}r==="clean_passes"&&(a=Number(a)),r==="edge_mopping"&&(a=a==="true"),this.card._state.updateEditorField(r,a),this.card._scheduleRender()}})},i._bindRoomEditorTransition=function(){this.card._onAll("[data-action='toggle-room-transition']","click",async e=>{e.stopPropagation();let t=e.currentTarget,r=t.dataset.roomId,a=t.dataset.value==="true";if(r)try{await this.card._actions.saveRoomTransition?.(r,a),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(n){console.error("[eufy-vacuum-command-center] Failed to save room transition flag:",n)}})},i._bindRoomEditorSave=function(){this.card._on(this.card.$("[data-action='save-room-editor']"),"click",async()=>{let e=this.card._state.activeEditorRoom(),t=this.card._state.editorFields();if(!(!e||!t))try{await this.card._actions.saveRoomEditor(e.mapId,e.id,t),this.card._state.setSkipRefreshOnClose(!0),await this._refreshRoomEditorEstimates(),this.card._state.closeRoomEditor(),this.card._scheduleRender()}catch(r){console.error("[eufy-vacuum-command-center] Failed to save room editor:",r)}})}}function ta(i){i._bindRoomRules=function(){let e=this.card.shadowRoot;e&&(e.querySelectorAll("[data-action='set-room-rules-tab']").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.roomId;r&&(this.card._state.setRoomRulesActiveRoom?.(r),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='open-new-rule']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.openNewRuleDraft?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='edit-rule']").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.ruleId,a=this.card._state.resolvedRoomRulesRoom?.();if(!a)return;let c=(this.card._state.roomRulesForRoom?.(a.id)??[]).find(s=>String(s.id)===String(r));c&&(this.card._state.openEditRuleDraft?.(c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='delete-rule']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.ruleId,a=this.card._state.resolvedRoomRulesRoom?.();if(!a||!r)return;let c=(this.card._state.roomRulesForRoom?.(a.id)??[]).filter(s=>String(s.id)!==String(r));try{await this.card._actions.saveRoomRules?.(a.mapId,a.id,c),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] Failed to delete rule:",s)}})}),e.querySelectorAll("[data-action='cancel-rule-editor']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.closeRulesDraft?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-field]").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.ruleField,a=t.dataset.ruleValue;if(r==null)return;let n;a===""?n=null:a==="true"?n=!0:a==="false"?n=!1:r==="effect.changes.clean_passes"?n=Number(a):n=a,this.card._state.updateRuleDraftField?.(r,n),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-input]").forEach(t=>{t.addEventListener("input",()=>{let r=t.dataset.ruleInput;r&&this.card._state.updateRuleDraftField?.(r,t.value)}),t.addEventListener("change",()=>{this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-select]").forEach(t=>{t.addEventListener("change",()=>{let r=t.dataset.ruleSelect;r&&(this.card._state.updateRuleDraftField?.(r,t.value||null),this.card._scheduleRender())})}),e.querySelectorAll("[data-rule-number-input]").forEach(t=>{t.addEventListener("input",()=>{let r=t.dataset.ruleNumberInput;if(!r)return;let a=t.value;this.card._state.updateRuleDraftField?.(r,a===""?null:Number(a))}),t.addEventListener("change",()=>{this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-multivalue]").forEach(t=>{t.addEventListener("click",()=>{let r=String(t.dataset.ruleMultivalue??"").trim();if(!r)return;let a=this.card._state.roomRulesDraft?.(),n=ra(a?.value),c=n.includes(r)?n.filter(s=>s!==r):[...n,r];this.card._state.updateRuleDraftField?.("value",c),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-entity-select]").forEach(t=>{t.addEventListener("click",()=>{let r=String(t.dataset.ruleEntitySelect??"").trim();r&&(this.card._state.updateRuleDraftField?.("entity_id",r),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='save-rule']").forEach(t=>{t.addEventListener("click",async()=>{let r=this.card._state;if(!r.roomRulesDraftIsValid?.())return;let a=r.resolvedRoomRulesRoom?.(),n=r.roomRulesDraft?.(),c=r.roomRulesDraftMode?.();if(!a||!n)return;let s=r.ruleEntityDescriptor?.(n),o=r.roomRulesForRoom?.(a.id)??[],l;c==="edit"&&n.id?l=o.map(d=>String(d.id)===String(n.id)?ea(n,s):d):l=[...o,ea(n,s)];try{let d=await this.card._actions.saveRoomRules?.(a.mapId,a.id,l);if(d?.ok===!1||d?.updated===!1){let u=d?.reason_detail??d?.message??d?.reason??"The backend rejected this rule.";r.setRoomRulesSaveError?.(u),this.card._scheduleRender();return}r.closeRulesDraft?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(d){console.error("[eufy-vacuum-command-center] Failed to save rule:",d),r.setRoomRulesSaveError?.("Failed to save rule. Check Home Assistant logs."),this.card._scheduleRender()}})}))}}function ea(i,e){let t={entity_id:String(i.entity_id??"").trim(),kind:i.kind??"blocker",operator:i.operator??"is_on",enabled:i.enabled!==!1,effect:{action:i.kind==="modifier"?"mutate":"exclude",reason:String(i.effect?.reason??"").trim()||null}};if(i.id&&(t.id=i.id),i.label?.trim()&&(t.label=i.label.trim()),!Ti.has(t.operator)&&i.value!=null){let r=ki(i.value,e,t.operator);(Array.isArray(r)?r.length:String(r).trim())&&(t.value=r)}if(i.kind==="modifier"){let r=i.effect?.changes??{},a={};for(let[n,c]of Object.entries(r))if(c!=null){if(n==="clean_passes"){let s=Number(c);(s===1||s===2)&&(a[n]=s);continue}a[n]=c}t.effect.changes=a}return t}function ki(i,e,t){let r=e?.valueModeForOperator?.(t)??"text";if(r==="multi-select")return ra(i);if(r==="number"){let a=Number(i);return Number.isFinite(a)?a:i}return i}function ra(i){if(Array.isArray(i))return i.map(t=>String(t??"").trim()).filter(Boolean);let e=String(i??"").trim();return e?e.split(",").map(t=>t.trim()).filter(Boolean):[]}var Ti=new Set(["is_on","is_off","exists","missing"]);var Ge=`

  .evcc-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--evcc-chip-gap, 6px);
  }

  .evcc-chip,
  .evcc-room-setting-chip,
  .evcc-room-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: var(--evcc-chip-height, 24px);
    padding: var(--evcc-chip-padding, 5px 14px);

    border-radius: var(--evcc-chip-radius, 999px);
    border: 1px solid var(--evcc-chip-border, var(--evcc-border-default));

    background: var(--evcc-chip-bg, var(--evcc-surface-input));
    color: var(--evcc-chip-text, var(--evcc-text-secondary));

    font-size: var(--evcc-chip-font-size, 0.82rem);
    font-weight: var(--evcc-chip-font-weight, 500);

    line-height: 1;
    white-space: nowrap;
    font-family: inherit;

    transition:
      background var(--evcc-transition-normal, 150ms ease),
      color var(--evcc-transition-normal, 150ms ease),
      border-color var(--evcc-transition-normal, 150ms ease),
      opacity var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-chip {
    cursor: pointer;
  }

  .evcc-chip:hover:not(:disabled):not(.active) {
    background: var(--evcc-chip-hover-bg, var(--evcc-surface-panel));
    color: var(--evcc-chip-hover-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-hover-border, var(--evcc-border-strong));
  }

  .evcc-chip.active {
    background: var(--evcc-chip-active-bg,
      color-mix(in srgb, var(--evcc-accent) 18%, transparent));
    color: var(--evcc-chip-active-text, var(--evcc-accent));
    border-color: var(--evcc-chip-active-border,
      color-mix(in srgb, var(--evcc-accent) 40%, transparent));
    font-weight: 600;
  }

  .evcc-chip:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .evcc-chip--icon {
    min-height: var(--evcc-chip-icon-height, 24px);
    padding: var(--evcc-chip-icon-padding, 4px 8px);
    font-size: var(--evcc-chip-icon-size, 0.8rem);
  }
`,aa=`

  :host {
    display: block;
    position: relative;
    height: 100%;
    min-height: 0;

    /* =======================================================
       CANONICAL FOUNDATION TOKENS
       ======================================================= */

    /* Surfaces */
    --evcc-surface-base:   var(--card-background-color, #1c2127);
    --evcc-surface-card:   var(--evcc-surface-base);
    --evcc-surface-panel:  color-mix(in srgb, var(--evcc-surface-base) 85%, white 15%);
    --evcc-surface-raised: color-mix(in srgb, var(--evcc-surface-base) 92%, white 8%);
    --evcc-surface-input:  rgba(255,255,255,0.06);
    --evcc-surface-overlay: rgba(0,0,0,0.4);

    /* Text */
    --evcc-text-primary:   var(--primary-text-color, #f0f2f5);
    --evcc-text-secondary: var(--secondary-text-color, rgba(240,242,245,0.72));
    --evcc-text-muted:     rgba(240,242,245,0.48);

    /* Borders */
    --evcc-border-subtle:  rgba(255,255,255,0.06);
    --evcc-border-default: rgba(255,255,255,0.10);
    --evcc-border-strong:  rgba(255,255,255,0.18);

    /* Accent */
    --evcc-accent: var(--accent-color, #3b82f6);

    /* Generic semantics */
    --evcc-sem-success: var(--success-color, #4caf6e);
    --evcc-sem-warning: var(--warning-color, #f5a623);
    --evcc-sem-error:   var(--error-color,   #e05252);

    /* Boundary confidence tiers
       Override these in theme editor to re-colour confidence indicators
       across all views without touching component code. */
    --evcc-conf-high:   var(--evcc-sem-success);
    --evcc-conf-mid:    var(--evcc-sem-warning);
    --evcc-conf-low:    var(--evcc-sem-error);
    --evcc-conf-none:   var(--evcc-text-muted);

    /* Radius */
    --evcc-radius-card:  var(--ha-card-border-radius, 12px);
    --evcc-radius-inner: 8px;
    --evcc-radius-chip:  999px;

    /* Spacing */
    --evcc-space-sm: 8px;
    --evcc-space-md: 12px;
    --evcc-space-lg: 16px;

    --evcc-gap: var(--evcc-space-md);
    --evcc-pad: var(--evcc-space-lg);

    /* =======================================================
       BACKWARD COMPATIBILITY (DO NOT REMOVE YET)
       ======================================================= */

    --evcc-card-bg:       var(--evcc-surface-card);
    --evcc-panel-bg:      var(--evcc-surface-panel);
    --evcc-surface-raise: var(--evcc-surface-raised);
    --evcc-bg-input:      var(--evcc-surface-input);
    --evcc-bg-panel:      var(--evcc-surface-panel);

    --evcc-border:        var(--evcc-border-default);

    /* Old status colors \u2192 mapped to semantics */
    --evcc-color-cleaning:  var(--evcc-sem-success);
    --evcc-color-docked:    var(--evcc-accent);
    --evcc-color-returning: var(--evcc-sem-warning);
    --evcc-color-error:     var(--evcc-sem-error);
    --evcc-color-paused:    var(--evcc-accent);
    --evcc-color-idle:      var(--evcc-text-secondary);

    /* =======================================================
       CHIP BASE TOKENS
       ======================================================= */

    --evcc-chip-height: 24px;
    --evcc-chip-padding: 5px 14px;
    --evcc-chip-radius: 999px;

    --evcc-chip-bg: var(--evcc-surface-input);
    --evcc-chip-border: var(--evcc-border-default);
    --evcc-chip-text: var(--evcc-text-secondary);

    --evcc-chip-hover-bg: var(--evcc-surface-panel);
    --evcc-chip-hover-text: var(--evcc-text-primary);
    --evcc-chip-hover-border: var(--evcc-border-strong);

    --evcc-chip-icon-height: 24px;
    --evcc-chip-icon-padding: 4px 8px;
    --evcc-chip-icon-size: 0.8rem;

    /* Motion */
    --evcc-transition-normal: 150ms ease;
  }

  /* =========================================================
     RESET
     ========================================================= */

  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  button {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  ha-card {
    contain: none !important;
    overflow: hidden !important;
    height: 100%;
    min-height: 0;
  }

  /* =========================================================
     CARD SHELL
     ========================================================= */

  .evcc-card {
    background: var(--evcc-surface-card);
    border-radius: var(--evcc-radius-card);
    color: var(--evcc-text-primary);
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
    font-size: 14px;
    line-height: 1.5;
    position: relative;
    isolation: isolate;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--evcc-gap);
    padding: var(--evcc-pad) var(--evcc-pad) 0;
    flex-wrap: wrap;
  }

  .evcc-vacuum-name {
    font-size: 1.1rem;
    font-weight: 600;
    line-height: 1.2;
  }

  .evcc-battery {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
  }

  /* =========================================================
     STATUS BADGE
     ========================================================= */

  .evcc-status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 500;

    background: var(--evcc-surface-raised);
    color: var(--evcc-text-secondary);
    border: 1px solid var(--evcc-border-default);
  }

  /* =========================================================
     NAVIGATION
     ========================================================= */

  .evcc-tab {
    padding: 6px 14px;
    border-radius: var(--evcc-radius-chip);
    font-size: 0.85rem;
    color: var(--evcc-text-secondary);
    transition: background 0.15s, color 0.15s;
  }

  .evcc-tab:hover {
    background: var(--evcc-surface-raised);
    color: var(--evcc-text-primary);
  }

  .evcc-tab.active {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    color: var(--evcc-accent);
    font-weight: 500;
  }

  .evcc-view {
    padding: var(--evcc-pad);
  }

  ${Ge}
`;var ia=`
  .evcc-base-station-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-base-station-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-base-station-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-base-station-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-base-station-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-base-station-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-base-station-panel-subtitle,
  .evcc-base-station-updated {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-base-station-stats,
  .evcc-base-station-activity-grid,
  .evcc-base-station-action-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-base-station-stat,
  .evcc-base-station-activity-card,
  .evcc-base-station-action-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-base-station-stat-value,
  .evcc-base-station-activity-time,
  .evcc-base-station-action-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-base-station-stat-label,
  .evcc-base-station-activity-title,
  .evcc-base-station-action-state {
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-base-station-activity-detail,
  .evcc-base-station-action-detail {
    font-size: 0.82rem;
    color: var(--evcc-text-muted);
    line-height: 1.45;
  }

  .evcc-base-station-action-card {
    width: 100%;
    text-align: left;
    cursor: pointer;
    transition:
      border-color var(--evcc-transition-normal, 150ms ease),
      transform var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-base-station-action-card:hover:not(:disabled) {
    border-color: var(--evcc-border-strong);
    transform: translateY(-1px);
  }

  .evcc-base-station-action-card--allowed {
    background: color-mix(in srgb, var(--evcc-sem-success) 8%, var(--evcc-surface-raised));
  }

  .evcc-base-station-action-card--blocked {
    cursor: default;
    opacity: 0.78;
  }

  @media (max-width: 720px) {
    .evcc-base-station-grid {
      grid-template-columns: 1fr;
    }

    .evcc-base-station-stats,
    .evcc-base-station-activity-grid,
    .evcc-base-station-action-grid {
      grid-template-columns: 1fr;
    }
  }
`;var na=`
  .evcc-metrics-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-metrics-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-metrics-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-metrics-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-metrics-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-metrics-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-panel-subtitle,
  .evcc-metrics-card-subtitle,
  .evcc-metrics-stat-label {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-metrics-stats,
  .evcc-metrics-filters,
  .evcc-metrics-window-grid,
  .evcc-metrics-card-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-metrics-stat,
  .evcc-metrics-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-metrics-stat-value,
  .evcc-metrics-card-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-card-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-metrics-card-header,
  .evcc-metrics-card-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-metrics-card-badge {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-metrics-card-detail,
  .evcc-metrics-card-secondary {
    font-size: 0.84rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-metrics-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-metrics-chip-filter {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-metrics-filter-chips {
    gap: 8px;
  }

  .evcc-metrics-tab-panel,
  .evcc-metrics-section-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .evcc-metrics-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  /* Battery sub-tab */

  .evcc-metrics-section-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--evcc-text-strong, var(--primary-text-color));
    margin-top: 4px;
  }

  .evcc-metrics-section-subtitle {
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
    line-height: 1.45;
    margin-top: -6px;
  }

  .evcc-metrics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .evcc-metrics-table th,
  .evcc-metrics-table td {
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid var(--evcc-border-default);
  }

  .evcc-metrics-table th {
    font-weight: 600;
    color: var(--evcc-text-muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-metrics-table tr:last-child td {
    border-bottom: none;
  }

  .evcc-metrics-table em {
    color: var(--evcc-text-muted);
    font-style: normal;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-metrics-codeblock {
    background: var(--evcc-bg-elevated, rgba(0, 0, 0, 0.18));
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 10px 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
    color: var(--evcc-text-default);
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
  }

  @media (max-width: 720px) {
    .evcc-metrics-grid,
    .evcc-metrics-stats,
    .evcc-metrics-filters,
    .evcc-metrics-window-grid,
    .evcc-metrics-card-grid {
      grid-template-columns: 1fr;
    }
  }
`;var ca=`
  .evcc-review-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-review-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-review-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-review-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-review-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-review-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-review-panel-subtitle {
    margin-top: 4px;
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-review-stats,
  .evcc-review-filters {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-review-matcher {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .evcc-review-chip-filter {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-review-reason-chips {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: min(100%, 460px);
  }

  .evcc-review-filter-chips {
    gap: 8px;
  }

  .evcc-review-matcher-grid {
    display: grid;
    gap: 14px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .evcc-review-matcher-field {
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-review-matcher-actions {
    display: flex;
    justify-content: flex-end;
  }

  .evcc-review-matcher-results {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: color-mix(in srgb, var(--evcc-surface-panel) 88%, white 12%);
  }

  .evcc-review-matcher-results-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-review-matcher-match-chips {
    gap: 8px;
  }

  .evcc-review-stat,
  .evcc-review-job-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-review-stat-value,
  .evcc-review-job-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-review-stat-label,
  .evcc-review-job-subtitle,
  .evcc-review-kv-label,
  .evcc-review-kv-subtitle {
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-review-job-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-review-job-card--excluded {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 28%, transparent);
  }

  .evcc-review-job-card--suggested {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 28%, transparent);
  }

  .evcc-review-job-header,
  .evcc-review-job-badges,
  .evcc-review-job-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
  }

  .evcc-review-job-badges {
    justify-content: flex-end;
  }

  .evcc-review-badge--excluded {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 14%, transparent);
    color: var(--evcc-sem-error);
  }

  .evcc-review-badge--suggested,
  .evcc-review-badge--warning {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-review-badge--neutral {
    border-color: var(--evcc-border-default);
    background: var(--evcc-surface-input);
    color: var(--evcc-text-secondary);
  }

  .evcc-review-job-grid {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .evcc-review-kv {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-review-kv-value,
  .evcc-review-job-note {
    font-size: 0.84rem;
    color: var(--evcc-text-primary);
    line-height: 1.5;
  }

  .evcc-review-job-note {
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: color-mix(in srgb, var(--evcc-surface-panel) 90%, white 10%);
  }

  .evcc-review-reason {
    min-width: 220px;
  }

  .evcc-review-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  @media (max-width: 720px) {
    .evcc-review-grid,
    .evcc-review-stats,
    .evcc-review-filters,
    .evcc-review-job-grid,
    .evcc-review-matcher-grid {
      grid-template-columns: 1fr;
    }
  }
`;var sa=`

  /* =========================================================
     OUTER SHELL
     ========================================================= */

  .evcc-shell {
    background:    var(--evcc-surface-card);
    border-radius: var(--evcc-radius-card);
    box-shadow:    var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    overflow:      hidden;
    display:       flex;
    flex-direction: column;
    height:        100%;
    min-height:    0;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         14px 16px 12px;
    border-bottom:   1px solid var(--evcc-border-subtle);
    gap:             var(--evcc-gap);
  }

  .evcc-header-left {
    display:       flex;
    flex-direction: column;
    gap:           2px;
    min-width:     0;
  }

  .evcc-vacuum-name {
    font-size:      1.05rem;
    font-weight:    600;
    color:          var(--evcc-text-primary);
    white-space:    nowrap;
    overflow:       hidden;
    text-overflow:  ellipsis;
  }

  .evcc-vacuum-status {
    display:     flex;
    align-items: center;
    gap:         6px;
    font-size:   0.8rem;
    color:       var(--evcc-text-secondary);
  }

  /* =========================================================
     STATUS DOT
     ========================================================= */

  .evcc-status-dot {
    width:         7px;
    height:        7px;
    border-radius: 50%;
    flex-shrink:   0;
    background:    var(--evcc-status-dot-idle, var(--evcc-text-muted));
    box-shadow:    var(--evcc-status-dot-shadow, none);
  }

  .evcc-status-dot.cleaning  { background: var(--evcc-status-dot-cleaning,   var(--evcc-sem-success)); }
  .evcc-status-dot.docked    { background: var(--evcc-status-dot-docked,     var(--evcc-accent)); }
  .evcc-status-dot.returning { background: var(--evcc-status-dot-returning,  var(--evcc-sem-warning)); }
  .evcc-status-dot.error     { background: var(--evcc-status-dot-error,      var(--evcc-sem-error)); }
  .evcc-status-dot.paused    { background: var(--evcc-status-dot-paused,     var(--evcc-accent)); }
  .evcc-status-dot.charging  { background: var(--evcc-status-dot-charging,   var(--evcc-sem-success)); }
  .evcc-status-dot.offline   { background: var(--evcc-status-dot-offline,    var(--evcc-text-muted)); }
  .evcc-status-dot.unavailable { background: var(--evcc-status-dot-unavailable, var(--evcc-text-muted)); }

  .evcc-battery {
    font-size:   0.78rem;
    color:       var(--evcc-text-muted);
    white-space: nowrap;
  }

  .evcc-battery.low {
    color: var(--evcc-sem-warning);
  }

  .evcc-battery.critical {
    color: var(--evcc-sem-error);
  }

  /* =========================================================
     NAV TABS
     ========================================================= */

  .evcc-nav {
    display:       flex;
    gap:           2px;
    padding:       8px 12px;
    border-bottom: 1px solid var(--evcc-border-subtle);
    background:    var(--evcc-surface-panel);
  }

  .evcc-nav-tab {
    flex:          1;
    padding:       6px 4px;
    border-radius: var(--evcc-radius-chip);
    font-size:     0.78rem;
    font-weight:   500;
    color:         var(--evcc-text-secondary);
    text-align:    center;
    transition:
      background var(--evcc-transition-normal, 150ms ease),
      color      var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-nav-tab:hover {
    background: var(--evcc-surface-raised);
    color:      var(--evcc-text-primary);
  }

  .evcc-nav-tab.active {
    background:  color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    color:       var(--evcc-accent);
    font-weight: 600;
  }

  /* =========================================================
     VIEW STAGE
     =========================================================
     The scrollable content area that each view renders into.
     ========================================================= */

  .evcc-view-stage {
    flex:       1;
    overflow-y: auto;
    padding:    var(--evcc-space-lg);
    min-height: 0;
    min-width:  0;
  }

  .evcc-view-stage[data-view="theme"] {
    display:    flex;
    overflow:   hidden;
    min-height: 0;
    height:     auto;
    max-height: none;
  }

  /* =========================================================
     EMPTY / PLACEHOLDER STATE
     ========================================================= */

  .evcc-empty {
    display:         flex;
    align-items:     center;
    justify-content: center;
    padding:         32px 16px;
    color:           var(--evcc-text-muted);
    font-size:       0.88rem;
    text-align:      center;
  }
`;var oa=`

  /* =========================================================
     SHARED GRID TOKENS
     ========================================================= */

  :host {
    --evcc-grid-gap:      12px;
    --evcc-room-grid-gap: var(--evcc-grid-gap);
    --evcc-room-grid-min: 240px;
  }

  /* =========================================================
     ROOM GRID
     =========================================================
     Reusable theme-aware grid primitive for the Rooms view.
     Future tabs can follow this same pattern with their own
     --evcc-<feature>-grid-* variables.
     ========================================================= */

  .evcc-room-grid {
    display: grid;
    gap: var(--evcc-room-grid-gap, var(--evcc-grid-gap, 12px));
    grid-template-columns: var(
      --evcc-room-grid-columns,
      repeat(auto-fit, minmax(var(--evcc-room-grid-min, 240px), 1fr))
    );
  }

  /* =========================================================
     RESPONSIVE SAFETY
     =========================================================
     On smaller screens, force a single column so cards never
     get too compressed even if a theme sets fixed columns.
     ========================================================= */

  @media (max-width: 720px) {
    .evcc-room-grid {
      grid-template-columns: 1fr;
    }
  }
`;var la=`

  /* =========================================================
     ORDER ROW / GROUPING
     ========================================================= */

  .evcc-order-controls {
    display: inline-flex;
    align-items: center;
    gap: var(--evcc-chip-gap, 6px);
    flex-wrap: wrap;
  }

  /* =========================================================
     ORDER CHIP
     ========================================================= */

  .evcc-order-chip {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.72rem;
    --evcc-chip-font-weight: 700;

    --evcc-chip-bg:     var(--evcc-order-chip-bg,
                          var(--evcc-chip-neutral-bg,
                          var(--evcc-surface-input)));

    --evcc-chip-border: var(--evcc-order-chip-border,
                          var(--evcc-border-default));

    --evcc-chip-text:   var(--evcc-order-chip-text,
                          var(--evcc-text-secondary));

    min-width:       34px;
    border-radius:   var(--evcc-radius-chip, 999px);
    line-height:     1;
    white-space:     nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* =========================================================
     MOVE BUTTON
     ========================================================= */

  .evcc-order-move-button {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.72rem;
    --evcc-chip-font-weight: 600;
  }

  /* =========================================================
     DRAG HANDLE
     ========================================================= */

  .evcc-order-drag-handle {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.78rem;
    --evcc-chip-font-weight: 700;

    cursor: grab;
    user-select: none;
    touch-action: none;
    letter-spacing: -0.08em;
    min-width: 30px;

    transition:
      background var(--evcc-transition-normal, 120ms ease),
      color var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-order-drag-handle:hover {
    background:   var(--evcc-chip-hover-bg, var(--evcc-surface-panel));
    color:        var(--evcc-chip-hover-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-hover-border, var(--evcc-border-strong));
  }

  .evcc-order-drag-handle:active {
    cursor: grabbing;
  }

  /* =========================================================
     SHARED CARD LIFT (MOTION ALIGNED)
     ========================================================= */

  .evcc-room-card {
    transition:
      transform    var(--evcc-transition-normal, 120ms ease),
      box-shadow   var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease),
      background   var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-room-card:hover {
    transform:  translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    box-shadow: var(--evcc-shadow-hover, 0 8px 18px rgba(0, 0, 0, 0.18));
  }

  /* =========================================================
     DRAG STATE
     ========================================================= */

  .evcc-order-drag-source {
    opacity:   var(--evcc-drag-opacity, 0.92);
    transform: scale(var(--evcc-drag-scale, 1.02));
    box-shadow: var(--evcc-drag-shadow, 0 14px 28px rgba(0, 0, 0, 0.25));
    z-index:   10;
  }

  .evcc-order-drag-target {
    outline:        1px dashed var(--evcc-order-target-outline,
                     color-mix(in srgb, var(--evcc-accent) 70%, transparent));
    outline-offset: 3px;
  }

  /* =========================================================
     REORDER FEEDBACK (FULL MOTION SYSTEM)
     ========================================================= */

  @keyframes evccOrderFeedbackPulse {
    0% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    }

    35% {
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--evcc-accent) 20%, transparent),
        var(--evcc-shadow-hover, 0 10px 22px rgba(0, 0, 0, 0.20));
    }

    100% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    }
  }

  .evcc-order-feedback {
    animation:
      evccOrderFeedbackPulse
      var(--evcc-reorder-feedback-duration, 700ms)
      var(--evcc-reorder-flip-easing, cubic-bezier(0.22, 1, 0.36, 1));

    border-color:
      var(--evcc-order-feedback-border,
      color-mix(in srgb, var(--evcc-accent) 55%, transparent)) !important;
  }

  /* =========================================================
     FEATURE-SAFE HELPERS
     ========================================================= */

  [data-order-drag-item] {
    -webkit-user-drag: element;
  }

  [data-order-drop-target] {
    position: relative;
    will-change: transform;
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 720px) {
    .evcc-order-drag-handle {
      display: none;
    }
  }
`;var da=`

  /* =========================================================
     ACTION BAR
     ========================================================= */

  .evcc-rooms-action-bar {
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-section-gap, 10px);
    padding-bottom: var(--evcc-space-md, 12px);
    border-bottom:  1px solid var(--evcc-border-default);
    margin-bottom:  var(--evcc-space-md, 12px);
  }

  .evcc-rooms-bar-top {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             var(--evcc-space-md, 12px);
    flex-wrap:       wrap;
  }

  .evcc-rooms-queue-summary {
    display:     flex;
    align-items: baseline;
    gap:         5px;
  }

  .evcc-rooms-queue-count {
    font-size:   1rem;
    font-weight: 600;
    color:       var(--evcc-text-primary);
  }

  .evcc-rooms-queue-label {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted);
  }

  /* =========================================================
     ACTION CHIPS
     ========================================================= */

  .evcc-chip--start:not([disabled]) {
    background:   var(--evcc-chip-success-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 36%, transparent));
    color:        var(--evcc-chip-success-text, var(--evcc-text-primary));
    border-color: var(--evcc-chip-success-border,
                    color-mix(in srgb, var(--evcc-sem-success) 55%, transparent));
    font-weight:  600;
  }

  .evcc-chip--start:not([disabled]):hover {
    background:   color-mix(in srgb, var(--evcc-sem-success) 50%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-success) 70%, transparent);
  }

  .evcc-chip--start-warn {
    background:   var(--evcc-chip-warning-bg,
                    color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent));
    color:        var(--evcc-chip-warning-text, var(--evcc-sem-warning));
    border-color: var(--evcc-chip-warning-border,
                    color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent));
    font-weight:  600;
  }

  .evcc-chip--start-warn:hover {
    background:   color-mix(in srgb, var(--evcc-sem-warning) 34%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 56%, transparent);
  }

  .evcc-chip--cancel-run {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 18%, transparent);
    color:        var(--evcc-sem-error, #ef4444);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 42%, transparent);
    font-weight:  600;
  }

  .evcc-chip--cancel-run:hover {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 26%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 58%, transparent);
  }

  .evcc-chip--confirm-flash {
    animation: evcc-room-confirm-pulse 1.25s ease-in-out infinite;
  }

  .evcc-rooms-block-reason {
    font-size: 0.8rem;
    color:     var(--evcc-sem-warning);
  }

  .evcc-rooms-inline-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .evcc-start-preflight-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 38%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent);
  }

  .evcc-start-preflight-header {
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-start-preflight-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-start-preflight-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-start-preflight-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-start-preflight-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-start-preflight-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    font-size: 0.78rem;
  }

  .evcc-start-preflight-room {
    font-weight: 600;
    color: var(--evcc-text-primary);
  }

  .evcc-start-preflight-reason {
    color: var(--evcc-text-secondary);
    text-align: right;
  }

  .evcc-queue-empty {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted);
  }

  /* =========================================================
     ACTIVE JOB
     ========================================================= */

  .evcc-active-job {
    display:        flex;
    flex-direction: column;
    gap:            8px;
    padding:        10px 12px;
    margin-bottom:  var(--evcc-space-md, 12px);
    border-radius:  var(--evcc-radius-panel, 14px);
    border:         1px solid var(--evcc-status-cleaning-border,
                    color-mix(in srgb, var(--evcc-sem-success) 35%, transparent));
    background:     var(--evcc-status-cleaning-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 10%, transparent));
  }

  .evcc-active-job-header {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-active-job-label {
    font-size:   0.82rem;
    font-weight: 600;
    color:       var(--evcc-status-cleaning-text, var(--evcc-sem-success));
  }

  .evcc-active-job-pulse {
    width:         8px;
    height:        8px;
    border-radius: 50%;
    background:    var(--evcc-status-dot-cleaning, var(--evcc-sem-success));
    box-shadow:    0 0 0 0 color-mix(in srgb, var(--evcc-status-dot-cleaning, var(--evcc-sem-success)) 55%, transparent);
    animation:     evccPulse var(--evcc-status-pulse-duration, 1.6s) infinite;
  }

  @keyframes evccPulse {
    0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-status-dot-cleaning, var(--evcc-sem-success)) 45%, transparent); }
    70%  { box-shadow: 0 0 0 10px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }

  @keyframes evcc-room-confirm-pulse {
    0%, 100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-sem-warning) 0%, transparent);
    }

    50% {
      box-shadow: 0 0 0 4px color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    }
  }

  /* =========================================================
     ROOM CARD
     ========================================================= */

  .evcc-room-card {
    position:        relative;
    overflow:        hidden;
    display:         flex;
    flex-direction:  column;
    gap:             var(--evcc-card-gap, 10px);
    min-height:      var(--evcc-card-min-height, 120px);
    padding:         var(--evcc-card-padding, 12px);
    border-radius:   var(--evcc-radius-card, 18px);
    border:          1px solid var(--evcc-border-default);
    background:      color-mix(in srgb, var(--evcc-surface-card) 84%, white 16%);
    box-shadow:      var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
    transition:
      transform      var(--evcc-transition-normal, 150ms ease),
      border-color   var(--evcc-transition-normal, 150ms ease),
      box-shadow     var(--evcc-transition-normal, 150ms ease),
      background     var(--evcc-transition-normal, 150ms ease);
    cursor:          pointer;
  }

  .evcc-room-card.is-enabled {
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--evcc-accent) 14%, transparent),
        color-mix(in srgb, var(--evcc-surface-card) 84%, white 16%)
      );
    box-shadow:
      0 0 0 1px color-mix(in srgb, var(--evcc-accent) 16%, transparent),
      var(--evcc-shadow-hover, 0 10px 20px rgba(0, 0, 0, 0.18));
  }

  .evcc-room-card:hover {
    transform:    translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    border-color: var(--evcc-border-strong);
  }

  .evcc-room-card:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--evcc-accent) 65%, transparent);
    outline-offset: 2px;
  }

  .evcc-room-card.is-enabled:hover {
    border-color: color-mix(in srgb, var(--evcc-accent) 52%, transparent);
  }

  .evcc-room-row {
    display: flex;
    align-items: center;
    width: 100%;
  }

  .evcc-room-row-1 {
    justify-content: flex-end;
  }

  .evcc-room-row-2 {
    justify-content: flex-start;
  }

  .evcc-room-controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .evcc-room-settings-hit-target {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    margin: -4px;
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    border-radius: 999px;
    position: relative;
    z-index: 2;
  }

  .evcc-room-settings-hit-target:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--evcc-accent) 65%, transparent);
    outline-offset: 2px;
  }

  .evcc-room-settings-button {
    pointer-events: none;
  }

  .evcc-room-name {
    font-size:     0.95rem;
    font-weight:   700;
    color:         var(--evcc-text-primary);
    line-height:   1.2;
    min-width:     0;
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  /* =========================================================
     ROOM DETAILS
     ========================================================= */

  .evcc-room-details {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-room-detail-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             10px;
    flex-wrap:       wrap;
  }

  .evcc-room-detail-label {
    font-size:   0.74rem;
    font-weight: 700;
    color:       var(--evcc-text-muted);
    min-width:   0;
  }

  /* =========================================================
     ROOM SETTING CHIPS
     ========================================================= */

  .evcc-room-setting-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       var(--evcc-chip-gap, 5px);
  }

  .evcc-room-setting-chip {
    --evcc-chip-height:      24px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.73rem;
    --evcc-chip-font-weight: 500;
    --evcc-chip-bg:          var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.06));
    --evcc-chip-border:      var(--evcc-room-chip-border, rgba(255, 255, 255, 0.10));
    --evcc-chip-text:        var(--evcc-room-chip-text, var(--evcc-text-secondary));
  }

  .evcc-room-setting-chip--profile {
    --evcc-chip-bg:     var(--evcc-profile-chip-bg, rgba(255, 255, 255, 0.08));
    --evcc-chip-border: var(--evcc-profile-chip-border, rgba(255, 255, 255, 0.14));
    --evcc-chip-text:   var(--evcc-profile-chip-text, var(--evcc-text-primary));
    font-weight: 600;
  }

  .evcc-room-setting-chip--profile.is-custom {
    --evcc-chip-bg:     var(--evcc-profile-chip-custom-bg,
                          color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent));
    --evcc-chip-border: var(--evcc-profile-chip-custom-border,
                          color-mix(in srgb, var(--evcc-sem-warning) 30%, transparent));
    --evcc-chip-text:   var(--evcc-profile-chip-custom-text, var(--evcc-sem-warning));
  }

  .evcc-room-card.is-enabled .evcc-room-setting-chip {
    --evcc-chip-bg:     var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.08));
    --evcc-chip-border: var(--evcc-room-chip-border, rgba(255, 255, 255, 0.14));
  }

  /* =========================================================
     STATUS CHIPS
     ========================================================= */

  .evcc-room-chip-row {
    display:    flex;
    gap:        8px;
    flex-wrap:  wrap;
    margin-top: auto;
  }

  .evcc-room-status {
    --evcc-chip-height:      24px;
    --evcc-chip-padding:     2px 10px;
    --evcc-chip-font-size:   0.74rem;
    --evcc-chip-font-weight: 700;
    cursor:                  default;
  }

  .evcc-room-status.is-included {
    --evcc-chip-bg:     var(--evcc-chip-included-bg,
                          color-mix(in srgb, var(--evcc-sem-success) 30%, transparent));
    --evcc-chip-text:   var(--evcc-chip-included-text, var(--evcc-sem-success));
    --evcc-chip-border: var(--evcc-chip-included-border,
                          color-mix(in srgb, var(--evcc-sem-success) 60%, transparent));
  }

  .evcc-room-status.is-excluded {
    --evcc-chip-bg:     var(--evcc-chip-excluded-bg,
                          color-mix(in srgb, var(--evcc-text-muted) 20%, transparent));
    --evcc-chip-text:   var(--evcc-chip-excluded-text, var(--evcc-text-secondary));
    --evcc-chip-border: var(--evcc-chip-excluded-border, var(--evcc-border-default));
  }

  .evcc-room-status.is-carpet {
    --evcc-chip-bg:     color-mix(in srgb, var(--evcc-accent) 22%, transparent);
    --evcc-chip-text:   var(--evcc-accent);
    --evcc-chip-border: color-mix(in srgb, var(--evcc-accent) 60%, transparent);
    cursor:             default;
  }

  /* =========================================================
     QUEUE CHIPS
     ========================================================= */

  .evcc-queue-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       var(--evcc-queue-chip-gap, 6px);
  }

  .evcc-queue-chip {
    all: unset;
    box-sizing: border-box;
    position:     relative;
    overflow:     hidden;

    display:       inline-flex;
    align-items:   center;
    gap:           6px;
    padding:       4px 10px;
    border-radius: 999px;

    background:    var(--evcc-queue-chip-bg, var(--evcc-surface-input));
    border:        1px solid var(--evcc-queue-chip-border, var(--evcc-border-default));
    color:         var(--evcc-queue-chip-text, var(--evcc-text-secondary));

    font-size:     0.78rem;
    white-space:   nowrap;
    cursor:        pointer;
    user-select:   none;
    touch-action:  manipulation;

    transition:
      transform    var(--evcc-transition-normal, 120ms ease),
      box-shadow   var(--evcc-transition-normal, 120ms ease),
      border-color var(--evcc-transition-normal, 120ms ease),
      background   var(--evcc-transition-normal, 120ms ease),
      color        var(--evcc-transition-normal, 120ms ease),
      opacity      var(--evcc-transition-normal, 120ms ease);
  }

  .evcc-queue-chip:hover {
    transform:    translateY(calc(-1 * var(--evcc-hover-lift, 1px)));
    background:   var(--evcc-queue-hover-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-hover-border,
                    color-mix(in srgb, var(--evcc-accent) 40%, transparent));
    color:        var(--evcc-queue-hover-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    box-shadow:   var(--evcc-shadow-hover, 0 6px 14px rgba(0, 0, 0, 0.18));
  }

  .evcc-queue-chip:active,
  .evcc-queue-chip.is-pressing {
    transform: scale(var(--evcc-press-scale, 0.97));
  }

  .evcc-queue-chip.is-long-pressing {
    background:   var(--evcc-chip-warning-bg,
                    color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent));
    border-color: var(--evcc-chip-warning-border,
                    color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent));
    color:        var(--evcc-chip-warning-text, var(--evcc-sem-warning));
  }

  .evcc-queue-chip--active {
    background:   var(--evcc-queue-current-bg,
                    color-mix(in srgb, var(--evcc-sem-success) 16%, transparent));
    border-color: var(--evcc-queue-current-border,
                    color-mix(in srgb, var(--evcc-sem-success) 32%, transparent));
    color:        var(--evcc-queue-current-text, var(--evcc-sem-success));
  }

  .evcc-queue-chip.is-pending {
    background:   var(--evcc-queue-pending-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-pending-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-pending-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    opacity:      var(--evcc-queue-pending-opacity, 1);
  }

  .evcc-queue-chip.is-current {
    background:   var(--evcc-queue-current-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-current-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-current-text, var(--evcc-queue-chip-text, var(--evcc-text-primary)));
    box-shadow:   var(--evcc-queue-current-glow, none);
  }

  .evcc-queue-chip.is-inferred {
    background:   var(--evcc-queue-inferred-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-inferred-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-inferred-text, var(--evcc-queue-chip-text, var(--evcc-text-primary)));
    box-shadow:   var(--evcc-queue-inferred-glow, none);
  }

  .evcc-queue-chip.is-completed {
    background:   var(--evcc-queue-completed-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-completed-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-completed-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
    opacity:      var(--evcc-queue-completed-opacity, 0.8);
  }

  .evcc-queue-chip.is-skipped {
    background:   var(--evcc-queue-skipped-bg, var(--evcc-queue-chip-bg, var(--evcc-surface-input)));
    border-color: var(--evcc-queue-skipped-border, var(--evcc-queue-chip-border, var(--evcc-border-default)));
    color:        var(--evcc-queue-skipped-text, var(--evcc-queue-chip-text, var(--evcc-text-secondary)));
  }

  .evcc-queue-chip-order {
    display:         inline-flex;
    align-items:     center;
    justify-content: center;
    min-width:       18px;
    height:          18px;
    padding:         0 5px;
    border-radius:   999px;
    background:      var(--evcc-queue-order-bg, rgba(255, 255, 255, 0.10));
    border:          1px solid var(--evcc-queue-order-border, transparent);
    font-size:       0.7rem;
    font-weight:     700;
    color:           var(--evcc-queue-order-text, currentColor);
  }

  .evcc-queue-chip-label {
    font-weight: 600;
    white-space: nowrap;
  }

  /* =========================================================
     EMPTY
     ========================================================= */

  .evcc-empty {
    padding:       24px;
    border-radius: var(--evcc-radius-panel, 16px);
    text-align:    center;
    color:         var(--evcc-text-muted);
    border:        1px dashed var(--evcc-border-default);
    background:    color-mix(in srgb, var(--evcc-surface-input) 50%, transparent);
  }

  /* =========================================================
     ROOM ESTIMATE TOKEN BRIDGE
     ========================================================= */

  :host {
    --evcc-estimate-learned-bg:
      color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    --evcc-estimate-learned-border:
      color-mix(in srgb, var(--evcc-accent) 30%, transparent);
    --evcc-estimate-learned-text:
      var(--evcc-text-primary);

    --evcc-estimate-default-bg:
      color-mix(in srgb, var(--evcc-text-muted) 12%, transparent);
    --evcc-estimate-default-border:
      var(--evcc-border-default);
    --evcc-estimate-default-text:
      var(--evcc-text-secondary);

    --evcc-learning-note-text:
      var(--evcc-text-muted);
    --evcc-learning-warning-text:
      var(--evcc-sem-warning);
  }

  /* =========================================================
     ROOM ESTIMATE CHIP
     ========================================================= */

  .evcc-room-status--estimate {
    border-style: solid;
  }

  .evcc-room-status--estimate-learned {
    background: var(--evcc-estimate-learned-bg);
    border-color: var(--evcc-estimate-learned-border);
    color: var(--evcc-estimate-learned-text);
  }

  .evcc-room-status--estimate-default {
    background: var(--evcc-estimate-default-bg);
    border-color: var(--evcc-estimate-default-border);
    color: var(--evcc-estimate-default-text);
    font-style: italic;
    opacity: 0.9;
  }

  /* =========================================================
     ROOM NOTES
     ========================================================= */

  .evcc-room-notes {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: var(--evcc-space-sm, 8px);
  }

  .evcc-room-note {
    font-size: 0.74rem;
    line-height: 1.25;
  }

  .evcc-room-note--muted {
    color: var(--evcc-learning-note-text);
  }

  .evcc-room-note--warning {
    color: var(--evcc-learning-warning-text);
    font-weight: 600;
  }
  
  /* =========================================================
     QUEUE CHIP CONFIDENCE TINT
     =========================================================
     Confidence is secondary to execution state.
     These classes should lightly tint queue chips without
     overpowering current/completed/remaining state styling.
     ========================================================= */

  .evcc-queue-chip--confidence-high {
    background:
      color-mix(in srgb, var(--evcc-confidence-high-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-high-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-high-bg) 45%, transparent);
  }

  .evcc-queue-chip--confidence-medium {
    background:
      color-mix(in srgb, var(--evcc-confidence-medium-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-medium-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-medium-bg) 45%, transparent);
  }

  .evcc-queue-chip--confidence-low {
    background:
      color-mix(in srgb, var(--evcc-confidence-low-bg) 30%, var(--evcc-surface-input));
    border-color: color-mix(in srgb, var(--evcc-confidence-low-border) 70%, var(--evcc-border-default));
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-confidence-low-bg) 45%, transparent);
  }

  /* =========================================================
     QUEUE CHIP TIME
     ========================================================= */

  .evcc-queue-chip-time {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    white-space: nowrap;
  }

  /* =========================================================
     QUEUE EXECUTION STATES
     ========================================================= */

  .evcc-queue-chip--queued {
    opacity: 0.95;
  }

  .evcc-queue-chip--remaining {
    opacity: 0.92;
  }

  .evcc-queue-chip--current {
    border-color: color-mix(in srgb, var(--evcc-accent) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-accent) 12%, transparent);
    color: var(--evcc-text-primary);
  }

  .evcc-queue-chip--completed {
    opacity: 0.72;
  }

  .evcc-queue-chip--completed .evcc-queue-chip-label,
  .evcc-queue-chip--completed .evcc-queue-chip-time {
    text-decoration: line-through;
  }

  /* =========================================================
     ROOM CARD CONFIDENCE LAYOUT
     ========================================================= */

  .evcc-room-chip-row .evcc-learning-chip {
    flex-shrink: 0;
  }

  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-rooms-bar-top {
      align-items: stretch;
    }

    .evcc-room-card {
      padding:       10px;
      border-radius: 16px;
    }

    .evcc-room-name {
      font-size: 0.88rem;
    }

    .evcc-room-status {
      --evcc-chip-height:    22px;
      --evcc-chip-padding:   2px 8px;
      --evcc-chip-font-size: 0.7rem;
    }
  }
  
  /* =========================================================
     QUEUE CHIP FILL
     ========================================================= */

  .evcc-queue-chip::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--job-progress, 0%);
    background: var(
      --evcc-progress-fill,
      color-mix(in srgb, var(--evcc-accent) 25%, transparent)
    );
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
  }

  .evcc-queue-chip > * {
    position: relative;
    z-index: 1;
  }

  /* =========================================================
     ROOM CARD FILL
     ========================================================= */

  .evcc-room-card::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--room-progress, 0%);
    background: var(
      --evcc-progress-fill,
      color-mix(in srgb, var(--evcc-accent) 15%, transparent)
    );
    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 0;
    opacity: var(--evcc-room-fill-opacity, 1);
  }

  .evcc-room-card > * {
    position: relative;
    z-index: 1;
  }

  /* =========================================================
     CURRENT ROOM ACTIVE GLOW / SHEEN
     ========================================================= */

  .evcc-room-card--queue-current::before {
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--evcc-accent) 20%, transparent),
      color-mix(in srgb, var(--evcc-accent) 35%, transparent)
    );
    animation: evcc-progress-pulse 2s ease-in-out infinite;
    will-change: opacity;
  }

  .evcc-room-card--queue-current::after,
  .evcc-queue-chip--current::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(
        110deg,
        transparent 0%,
        color-mix(in srgb, white 28%, transparent) 45%,
        transparent 70%
      );
    transform: translateX(-130%);
    animation: evcc-progress-sheen 2.4s linear infinite;
    pointer-events: none;
    z-index: 0;
  }

  @keyframes evcc-progress-pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
  }

  @keyframes evcc-progress-sheen {
    0%   { transform: translateX(-130%); }
    100% { transform: translateX(130%); }
  }

  .evcc-queue-chip--current::before {
    animation: evcc-progress-pulse 2s ease-in-out infinite;
  }

  /* =========================================================
     COMPLETED STATE + SWEEP
     ========================================================= */

  .evcc-room-card--queue-completed::before {
    width: 100%;
    background: var(
      --evcc-progress-complete,
      color-mix(in srgb, var(--evcc-sem-success) 30%, transparent)
    );
  }

  .evcc-queue-chip--completed::before {
    width: 100%;
    background: var(
      --evcc-progress-complete,
      color-mix(in srgb, var(--evcc-sem-success) 35%, transparent)
    );
  }

  .evcc-room-card--queue-completed::after,
  .evcc-queue-chip--completed::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(
        100deg,
        transparent 0%,
        color-mix(in srgb, white 35%, transparent) 48%,
        transparent 75%
      );
    transform: translateX(-140%);
    animation: evcc-progress-complete-sweep 800ms ease-out 1;
    pointer-events: none;
    z-index: 0;
  }

  @keyframes evcc-progress-complete-sweep {
    0%   { transform: translateX(-140%); opacity: 0; }
    15%  { opacity: 1; }
    100% { transform: translateX(140%); opacity: 0; }
  }

  /* =========================================================
     REMAINING FAINT TINT STATE
     ========================================================= */
   
  .evcc-room-card--queue-remaining::before {
    background: color-mix(in srgb, var(--evcc-accent) 6%, transparent);
  }

  /* =========================================================
     CONFIDENCE-AWARE FILL INTENSITY
     ========================================================= */

  .evcc-room-card--confidence-high {
    --evcc-room-fill-opacity: 1;
  }

  .evcc-room-card--confidence-medium {
    --evcc-room-fill-opacity: 0.82;
  }

  .evcc-room-card--confidence-low {
    --evcc-room-fill-opacity: 0.66;
  }

  /* =========================================================
     LIVE PROGRESS MICRO TEXT
     ========================================================= */

  .evcc-room-progress-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
  }

  .evcc-room-progress-chip {
    --evcc-chip-height:      22px;
    --evcc-chip-padding:     2px 8px;
    --evcc-chip-font-size:   0.7rem;
    --evcc-chip-font-weight: 700;
    --evcc-chip-bg:          color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    --evcc-chip-border:      color-mix(in srgb, var(--evcc-accent) 30%, transparent);
    --evcc-chip-text:        var(--evcc-text-primary);
  }

  .evcc-room-progress-chip--remaining {
    --evcc-chip-bg:     color-mix(in srgb, var(--evcc-text-muted) 14%, transparent);
    --evcc-chip-border: color-mix(in srgb, var(--evcc-text-muted) 28%, transparent);
    --evcc-chip-text:   var(--evcc-text-secondary);
  }

  /* =========================================================
     REDUCED MOTION
     ========================================================= */

  @media (prefers-reduced-motion: reduce) {
    .evcc-room-card,
    .evcc-queue-chip,
    .evcc-room-card::before,
    .evcc-queue-chip::before {
      transition-duration: 0.01ms !important;
    }

    .evcc-room-card--queue-current::before,
    .evcc-queue-chip--current::before,
    .evcc-room-card--queue-current::after,
    .evcc-queue-chip--current::after,
    .evcc-room-card--queue-completed::after,
    .evcc-queue-chip--completed::after,
    .evcc-active-job-pulse {
      animation: none !important;
    }
  }

  /* =========================================================
     ORPHANED ROOMS PANEL
     ========================================================= */

  .evcc-orphaned-rooms-panel {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--evcc-space-sm, 8px);
    padding: 8px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid color-mix(in srgb, var(--evcc-text-muted) 25%, transparent);
    background: color-mix(in srgb, var(--evcc-text-muted) 8%, transparent);
    margin-bottom: var(--evcc-space-md, 12px);
  }

  .evcc-orphaned-rooms-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--evcc-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .evcc-orphaned-rooms-chips {
    gap: 6px;
    flex: 1;
  }

  .evcc-orphaned-rooms-chip {
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
    border-color: color-mix(in srgb, var(--evcc-text-muted) 30%, transparent);
    background: transparent;
    cursor: default;
    pointer-events: none;
  }
`;var Ue=`
  .evcc-room-access-modal {
    max-width: 560px;
  }

  .evcc-room-access-section,
  .evcc-room-access-issues {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-panel) 85%, transparent);
  }

  .evcc-room-access-help {
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-room-access-chip-grid {
    gap: 8px;
  }

  .evcc-room-access-chip {
    transition:
      background var(--evcc-transition-normal, 150ms ease),
      border-color var(--evcc-transition-normal, 150ms ease),
      color var(--evcc-transition-normal, 150ms ease),
      opacity var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-room-access-chip:not(.active):not(.evcc-room-access-chip--readonly) {
    opacity: 0.72;
  }

  .evcc-room-access-chip--readonly {
    cursor: default;
    opacity: 0.92;
  }

  .evcc-room-access-chip--missing {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 45%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-room-access-chip--claimed {
    opacity: 0.35;
    cursor: not-allowed;
    pointer-events: none;
  }

  .evcc-room-access-issue-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-room-access-issue,
  .evcc-room-access-save-error,
  .evcc-room-access-empty {
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .evcc-room-access-issue,
  .evcc-room-access-save-error {
    color: var(--evcc-sem-warning);
  }

  .evcc-room-access-save-error {
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 32%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, transparent);
  }

  .evcc-room-access-empty {
    color: var(--evcc-text-muted);
  }
`;var We=`
  .evcc-room-estimate-modal {
    max-width: 560px;
  }

  .evcc-room-estimate-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .evcc-room-estimate-subtitle {
    margin-top: 4px;
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
    font-size: 0.88rem;
  }

  .evcc-room-estimate-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-room-estimate-grid {
    display: grid;
    gap: 8px;
  }

  .evcc-room-estimate-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 12px;
    border: 1px solid var(--evcc-modal-border-subtle, var(--evcc-border-subtle));
    border-radius: 12px;
    background: color-mix(in srgb, var(--evcc-modal-surface-panel, var(--evcc-surface-panel)) 82%, transparent);
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
  }

  .evcc-room-estimate-row span:last-child {
    color: var(--evcc-modal-text-primary, var(--evcc-text-primary));
    font-weight: 600;
    text-align: right;
  }

  .evcc-room-estimate-notes {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-room-estimate-note,
  .evcc-room-estimate-empty {
    padding: 12px 14px;
    border-radius: 12px;
    border: 1px dashed var(--evcc-modal-border-subtle, var(--evcc-border-subtle));
    color: var(--evcc-modal-text-secondary, var(--evcc-text-secondary));
    background: color-mix(in srgb, var(--evcc-modal-surface-panel, var(--evcc-surface-panel)) 70%, transparent);
  }
`;var ua=`

/* ============================================================
   ROOM RULES VIEW
   ============================================================ */

.evcc-room-rules-view {
  display:        flex;
  flex-direction: column;
  gap:            0;
  min-height:     0;
}

/* =========================================================
   SUB-TABS
   ========================================================= */

.evcc-room-rules-subtabs {
  display:              flex;
  gap:                  4px;
  overflow-x:           auto;
  padding:              12px 16px 0;
  scrollbar-width:      none;
  flex-shrink:          0;
  border-bottom:        1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
}

.evcc-room-rules-subtabs::-webkit-scrollbar {
  display: none;
}

.evcc-room-rules-subtab {
  display:         flex;
  align-items:     center;
  gap:             6px;
  padding:         6px 14px;
  border-radius:   8px 8px 0 0;
  font-size:       0.82rem;
  font-weight:     500;
  color:           var(--evcc-text-secondary, rgba(240,242,245,0.72));
  background:      transparent;
  border:          1px solid transparent;
  border-bottom:   none;
  cursor:          pointer;
  white-space:     nowrap;
  transition:      background 120ms ease, color 120ms ease;
}

.evcc-room-rules-subtab:hover {
  background: var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:      var(--evcc-text-primary, #f0f2f5);
}

.evcc-room-rules-subtab.active {
  background:   var(--evcc-surface-input, rgba(255,255,255,0.08));
  color:        var(--evcc-text-primary, #f0f2f5);
  border-color: var(--evcc-border-default, rgba(255,255,255,0.10));
  font-weight:  600;
}

.evcc-room-rules-subtab-count {
  display:          inline-flex;
  align-items:      center;
  justify-content:  center;
  min-width:        18px;
  height:           18px;
  padding:          0 5px;
  border-radius:    999px;
  font-size:        0.72rem;
  font-weight:      700;
  background:       color-mix(in srgb, var(--evcc-accent, #3b82f6) 20%, transparent);
  color:            var(--evcc-accent, #3b82f6);
}

/* =========================================================
   CONTENT AREA
   ========================================================= */

.evcc-room-rules-content {
  padding:    16px;
  flex:       1;
  min-height: 0;
  overflow-y: auto;
}

/* ============================================================
   RULE LIST
   ============================================================ */

.evcc-rule-list {
  display:        flex;
  flex-direction: column;
  gap:            8px;
}

.evcc-rule-list-empty {
  font-size: 0.88rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  padding:   8px 0;
}

.evcc-rule-list-actions {
  padding-top: 4px;
}

/* =========================================================
   RULE CARD
   ========================================================= */

.evcc-rule-card {
  display:        flex;
  flex-direction: column;
  gap:            8px;
  padding:        10px 12px;
  border-radius:  10px;
  border:         1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:     var(--evcc-surface-input, rgba(255,255,255,0.04));
}

.evcc-rule-card--disabled {
  opacity: 0.55;
}

.evcc-rule-card-body {
  display:     flex;
  align-items: flex-start;
  gap:         10px;
}

.evcc-rule-card-actions {
  display:     flex;
  gap:         6px;
  justify-content: flex-end;
}

.evcc-rule-kind-badge {
  flex-shrink:   0;
  padding:       2px 8px;
  border-radius: 999px;
  font-size:     0.68rem;
  font-weight:   700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.evcc-rule-kind-badge--blocker {
  background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 18%, transparent);
  color:      var(--evcc-sem-error, #ef4444);
  border:     1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 35%, transparent);
}

.evcc-rule-kind-badge--modifier {
  background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
  color:      var(--evcc-accent, #3b82f6);
  border:     1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 35%, transparent);
}

.evcc-rule-info {
  flex:    1;
  display: flex;
  flex-direction: column;
  gap:     2px;
  min-width: 0;
}

.evcc-rule-label {
  font-size:   0.88rem;
  font-weight: 600;
  color:       var(--evcc-text-primary, #f0f2f5);
  overflow:    hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evcc-rule-entity {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  overflow:  hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evcc-rule-condition {
  font-size:  0.80rem;
  color:      var(--evcc-text-secondary, rgba(240,242,245,0.72));
  margin-top: 2px;
}

.evcc-rule-effect {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
}

.evcc-rule-disabled-tag {
  flex-shrink:   0;
  align-self:    center;
  padding:       2px 7px;
  border-radius: 999px;
  font-size:     0.68rem;
  font-weight:   600;
  background:    rgba(255,255,255,0.06);
  color:         var(--evcc-text-muted, rgba(240,242,245,0.48));
  border:        1px solid rgba(255,255,255,0.08);
}

.evcc-chip--danger {
  color:        var(--evcc-sem-error, #ef4444);
  border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 35%, transparent);
}

.evcc-chip--danger:hover {
  background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 50%, transparent);
}

/* ============================================================
   RULE EDITOR FORM
   ============================================================ */

.evcc-rule-editor {
  display:        flex;
  flex-direction: column;
  gap:            0;
  border-radius:  12px;
  border:         1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:     var(--evcc-surface-input, rgba(255,255,255,0.03));
  overflow:       hidden;
}

.evcc-rule-editor-header {
  padding:       12px 16px;
  border-bottom: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
  flex-shrink:   0;
}

.evcc-rule-editor-title {
  font-size:   0.95rem;
  font-weight: 700;
  color:       var(--evcc-text-primary, #f0f2f5);
}

.evcc-rule-editor-body {
  display:        flex;
  flex-direction: column;
  gap:            20px;
  padding:        16px;
  overflow-y:     auto;
}

.evcc-rule-editor-section {
  display:        flex;
  flex-direction: column;
  gap:            8px;
}

.evcc-rule-editor-help {
  font-size: 0.78rem;
  color:     var(--evcc-text-muted, rgba(240,242,245,0.48));
  line-height: 1.5;
}

.evcc-rule-entity-search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
  padding: 8px;
  border-radius: 10px;
  border: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
  background: var(--evcc-surface-panel, rgba(255,255,255,0.02));
}

.evcc-rule-entity-search-result {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
  background: transparent;
  text-align: left;
  transition: background 120ms ease, border-color 120ms ease;
}

.evcc-rule-entity-search-result:hover {
  background: var(--evcc-surface-input, rgba(255,255,255,0.05));
  border-color: var(--evcc-border-default, rgba(255,255,255,0.12));
}

.evcc-rule-entity-search-result.active {
  background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 10%, transparent);
  border-color: color-mix(in srgb, var(--evcc-accent, #3b82f6) 30%, transparent);
}

.evcc-rule-entity-search-title {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--evcc-text-primary, #f0f2f5);
}

.evcc-rule-entity-search-meta,
.evcc-rule-entity-search-empty {
  font-size: 0.75rem;
  color: var(--evcc-text-muted, rgba(240,242,245,0.48));
}

.evcc-rule-entity-search-empty {
  padding: 8px 0;
}

.evcc-rule-editor-optional {
  font-size:   0.72rem;
  font-weight: 400;
  color:       var(--evcc-text-muted, rgba(240,242,245,0.48));
}

.evcc-rule-editor-input {
  width:        100%;
  padding:      7px 10px;
  border-radius: 6px;
  border:       1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
  background:   var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:        var(--evcc-text-primary, #f0f2f5);
  font-size:    0.88rem;
  font-family:  inherit;
  outline:      none;
  transition:   border-color 120ms ease;
}

.evcc-rule-editor-input:focus {
  border-color: var(--evcc-accent, #3b82f6);
}

.evcc-rule-editor-input--error {
  border-color: var(--evcc-sem-error, #ef4444);
}

.evcc-rule-operator-group {
  display:        flex;
  flex-direction: column;
  gap:            4px;
}

.evcc-rule-operator-group-label {
  font-size:  0.72rem;
  font-weight: 500;
  color:      var(--evcc-text-muted, rgba(240,242,245,0.48));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* =========================================================
   MODIFIER CHANGES
   ========================================================= */

.evcc-rule-change-row {
  display:        flex;
  flex-direction: column;
  gap:            6px;
}

.evcc-rule-change-label {
  font-size:   0.78rem;
  font-weight: 500;
  color:       var(--evcc-text-secondary, rgba(240,242,245,0.72));
}

.evcc-chip--muted {
  opacity: 0.55;
}

.evcc-chip--muted.active {
  opacity: 1;
  background: var(--evcc-surface-input, rgba(255,255,255,0.08));
  color:      var(--evcc-text-muted, rgba(240,242,245,0.48));
  border-color: var(--evcc-border-default, rgba(255,255,255,0.10));
}

/* =========================================================
   FOOTER
   ========================================================= */

.evcc-rule-editor-save-error {
  margin:       0 16px;
  padding:      8px 12px;
  border-radius: 6px;
  font-size:    0.82rem;
  font-weight:  500;
  background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 30%, transparent);
  color:        var(--evcc-sem-error, #ef4444);
}

.evcc-rule-editor-footer {
  display:         flex;
  align-items:     center;
  justify-content: flex-end;
  gap:             8px;
  padding:         12px 16px;
  border-top:      1px solid var(--evcc-border-subtle, rgba(255,255,255,0.06));
  flex-shrink:     0;
}

/* ============================================================
   LIGHT MODE OVERRIDES
   ============================================================ */

@media (prefers-color-scheme: light) {
  .evcc-room-rules-subtab.active {
    background: rgba(15,23,42,0.05);
    color:      #0f172a;
  }

  .evcc-rule-card {
    background: rgba(15,23,42,0.03);
    border-color: rgba(15,23,42,0.10);
  }

  .evcc-rule-editor {
    background: rgba(15,23,42,0.02);
    border-color: rgba(15,23,42,0.10);
  }

  .evcc-rule-editor-input {
    background:   rgba(15,23,42,0.05);
    border-color: rgba(15,23,42,0.10);
    color:        #0f172a;
  }
}
`;var ma=`
  .evcc-rooms-workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 16px;
    align-items: start;
  }

  .evcc-rooms-main {
    min-width: 0;
  }

  .evcc-run-profiles-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--evcc-radius-panel, 16px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    box-shadow: var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));
  }

  .evcc-run-profiles-panel-header {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-run-profiles-title {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-subtitle {
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-editor,
  .evcc-run-profiles-selected {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-input) 72%, transparent);
  }

  .evcc-run-profiles-editor-title,
  .evcc-run-profiles-selected-name {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-run-profiles-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-run-profiles-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-run-profiles-input {
    width: 100%;
    min-height: 38px;
    padding: 0 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-primary);
    font: inherit;
  }

  .evcc-run-profiles-toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-run-profiles-editor-actions,
  .evcc-run-profiles-selected-actions,
  .evcc-run-profiles-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-run-profiles-selected-meta,
  .evcc-run-profiles-selected-summary,
  .evcc-run-profiles-empty {
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  @media (max-width: 980px) {
    .evcc-rooms-workspace {
      grid-template-columns: 1fr;
    }
  }
`;var Je=`
  .evcc-maintenance-modal {
    max-width: 560px;
  }

  .evcc-maintenance-modal-hero {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 10px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-raised) 92%, white 8%);
  }

  .evcc-maintenance-modal-hero--status-good {
    background: color-mix(in srgb, var(--evcc-sem-success) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero--status-warning,
  .evcc-maintenance-modal-hero--status-replace_soon {
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero--status-replace_now {
    background: color-mix(in srgb, var(--evcc-sem-error) 12%, var(--evcc-surface-raised));
  }

  .evcc-maintenance-modal-hero-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-modal-hero-label,
  .evcc-maintenance-modal-hero-status {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-modal-hero-value {
    font-size: 1.18rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-modal-hero-detail {
    font-size: 0.85rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-modal-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-maintenance-guide-list,
  .evcc-maintenance-guide-notes {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-maintenance-guide-list {
    margin: 0;
    padding-left: 18px;
  }

  .evcc-maintenance-guide-item,
  .evcc-maintenance-guide-note,
  .evcc-maintenance-reset-hint {
    font-size: 0.86rem;
    line-height: 1.55;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-guide-note,
  .evcc-maintenance-reset-hint {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-maintenance-reset-hint--success {
    border-color: color-mix(in srgb, var(--evcc-sem-success) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-success) 10%, var(--evcc-surface-raised));
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-reset-hint--error {
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 10%, var(--evcc-surface-raised));
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-reset-meta,
  .evcc-maintenance-reset-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
`,va=`
  .evcc-maintenance-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-maintenance-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: 1fr;
  }

  .evcc-maintenance-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-maintenance-panel--wide {
    grid-column: 1 / -1;
  }

  .evcc-maintenance-panel--placeholder {
    border-style: dashed;
    opacity: 0.9;
  }

  .evcc-maintenance-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-meta-badge {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    min-height: var(--evcc-chip-height, 24px);
    padding: var(--evcc-chip-padding, 5px 14px);
    border-radius: var(--evcc-chip-radius, 999px);
    border: 1px solid var(--evcc-chip-border, var(--evcc-border-default));
    background: var(--evcc-chip-bg, var(--evcc-surface-input));
    color: var(--evcc-chip-text, var(--evcc-text-secondary));
    font-size: 0.8rem;
    font-weight: 600;
    line-height: 1;
  }

  .evcc-maintenance-model-line {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-panel-title {
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-panel-subtitle {
    margin-top: 4px;
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-stats {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evcc-maintenance-stat {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
  }

  .evcc-maintenance-stat-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-stat-label {
    margin-top: 4px;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--evcc-text-muted);
  }

  .evcc-maintenance-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-maintenance-grid > .evcc-maintenance-panel:nth-child(1),
  .evcc-maintenance-grid > .evcc-maintenance-panel:nth-child(2) {
    min-height: 100%;
  }

  .evcc-maintenance-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-maintenance-tab-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-maintenance-tab-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-maintenance-card-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .evcc-maintenance-card {
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 120px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: color-mix(in srgb, var(--evcc-surface-raised) 92%, white 8%);
    width: 100%;
    text-align: left;
    cursor: pointer;
  }

  .evcc-maintenance-card::before {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--maintenance-remaining, 0%);
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    z-index: 0;
    transition:
      width var(--evcc-transition-normal, 150ms ease),
      background var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-maintenance-card > * {
    position: relative;
    z-index: 1;
  }

  .evcc-maintenance-card--status-good::before {
    background: color-mix(in srgb, var(--evcc-sem-success) 16%, transparent);
  }

  .evcc-maintenance-card--status-warning::before,
  .evcc-maintenance-card--status-replace_soon::before {
    background: color-mix(in srgb, var(--evcc-sem-warning) 20%, transparent);
  }

  .evcc-maintenance-card--status-replace_now::before {
    background: color-mix(in srgb, var(--evcc-sem-error) 22%, transparent);
  }

  .evcc-maintenance-card--unavailable {
    opacity: 0.7;
  }

  .evcc-maintenance-card:hover,
  .evcc-maintenance-item:hover {
    border-color: var(--evcc-border-strong);
  }

  .evcc-maintenance-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-maintenance-card-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-card-status {
    flex-shrink: 0;
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-card-value {
    font-size: 1.08rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-card-detail {
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary);
  }

  .evcc-maintenance-card-secondary {
    margin-top: auto;
    font-size: 0.78rem;
    color: var(--evcc-text-muted);
  }

  .evcc-maintenance-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle);
    background: var(--evcc-surface-raised);
    width: 100%;
    text-align: left;
    cursor: pointer;
  }

  .evcc-maintenance-item-main {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-maintenance-item-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--evcc-text-primary);
  }

  .evcc-maintenance-item-detail {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-item-side {
    flex-shrink: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-align: right;
  }

  .evcc-maintenance-item-detail {
    font-size: 0.8rem;
    color: var(--evcc-text-secondary);
    line-height: 1.45;
  }

  .evcc-maintenance-empty {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px dashed var(--evcc-border-default);
    color: var(--evcc-text-muted);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  ${Je}

  @media (max-width: 720px) {
    .evcc-maintenance-grid {
      grid-template-columns: 1fr;
    }

    .evcc-maintenance-stats {
      grid-template-columns: 1fr;
    }
  }
`;var pa=`

  /* =========================================================
     BACKDROP
     ========================================================= */

  .evcc-modal-backdrop {
    position: absolute;
    inset:    0;

    background:
      var(--evcc-modal-backdrop-bg,
      rgba(0, 0, 0, 0.72));

    backdrop-filter:
      blur(var(--evcc-modal-backdrop-blur, 8px));

    display:         flex;
    align-items:     flex-start;
    justify-content: center;
    padding:         60px 16px 16px;
    z-index:         999;
  }

  /* =========================================================
     MODAL SHELL
     ========================================================= */

  .evcc-modal {
    background:
      var(--evcc-modal-bg,
      #1c2127);

    border:
      1px solid var(--evcc-modal-border,
      rgba(255, 255, 255, 0.18));

    border-radius: var(--evcc-modal-radius, 18px);

    box-shadow:
      var(--evcc-modal-shadow,
      0 20px 60px rgba(0, 0, 0, 0.60));

    width:         100%;
    max-width:     480px;
    max-height:    calc(100% - 76px);
    display:       flex;
    flex-direction: column;
    overflow:      hidden;

    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-modal-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         var(--evcc-modal-padding, 14px 16px 12px);
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-default));
    flex-shrink:     0;
    gap:             12px;
    background:
      var(--evcc-modal-header-bg,
      transparent);
  }

  .evcc-modal-title {
    font-size:      1rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
    min-width:      0;
    overflow:       hidden;
    text-overflow:  ellipsis;
    white-space:    nowrap;
  }

  /* =========================================================
     BODY
     ========================================================= */

  .evcc-modal-body {
    flex:           1;
    min-height:     0;
    overflow-y:     auto;
    padding:        var(--evcc-modal-padding, 14px 16px);
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-modal-section-gap, 16px);
    background:
      var(--evcc-modal-surface-section,
      transparent);
  }

  /* =========================================================
     FOOTER
     ========================================================= */

  .evcc-modal-footer {
    display:         flex;
    align-items:     center;
    justify-content: flex-end;
    gap:             8px;
    padding:         var(--evcc-modal-padding, 12px 16px 14px);
    border-top:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-default));
    flex-shrink:     0;
    background:
      var(--evcc-modal-footer-bg,
      transparent);
  }

  /* =========================================================
     SAVE CHIP (MODAL ACTION)
     ========================================================= */

  .evcc-chip--save {
    background:
      var(--evcc-modal-chip-active-bg,
      var(--evcc-modal-accent-bg,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 22%, transparent)));

    color:
      var(--evcc-modal-chip-active-text,
      var(--evcc-modal-accent-text,
      var(--evcc-modal-accent, var(--evcc-accent))));

    border-color:
      var(--evcc-modal-chip-active-border,
      var(--evcc-modal-accent-border,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 45%, transparent)));

    font-weight: 600;
  }

  .evcc-chip--save:hover {
    background:
      var(--evcc-modal-chip-hover-bg,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 34%, transparent));

    color:
      var(--evcc-modal-chip-hover-text,
      var(--evcc-modal-accent-text,
      var(--evcc-modal-accent, var(--evcc-accent))));

    border-color:
      var(--evcc-modal-chip-hover-border,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 60%, transparent));
  }

  /* =========================================================
     FIELD GROUPS
     ========================================================= */

  .evcc-editor-field-group {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-field-label {
    font-size:      0.75rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* =========================================================
     ROOM EDITOR SPECIFICS
     ========================================================= */

  .evcc-room-editor-carpet-notice {
    display:       flex;
    align-items:   center;
    gap:           8px;
    padding:       8px 12px;
    border-radius: 10px;

    background:
      var(--evcc-modal-warning-bg,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning)) 14%, transparent));

    border:
      1px solid var(--evcc-modal-warning-border,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning)) 35%, transparent));

    color:
      var(--evcc-modal-warning-text,
      var(--evcc-sem-warning));

    font-size:   0.8rem;
    font-weight: 500;
  }

  .evcc-room-editor-transition-callout {
    padding:       7px 11px;
    border-radius: 8px;
    background:    color-mix(in srgb, var(--evcc-text-muted) 10%, transparent);
    border:        1px solid color-mix(in srgb, var(--evcc-text-muted) 22%, transparent);
    color:         var(--evcc-text-muted);
    font-size:     0.78rem;
    line-height:   1.4;
    margin-bottom: 6px;
  }

  .evcc-chip--custom {
    background:
      var(--evcc-modal-chip-bg,
      color-mix(in srgb, var(--evcc-modal-text-muted, var(--evcc-text-muted)) 14%, transparent));

    color:
      var(--evcc-modal-chip-text,
      var(--evcc-modal-text-secondary, var(--evcc-text-secondary)));

    border-color:
      var(--evcc-modal-chip-border,
      var(--evcc-modal-border-strong, var(--evcc-border-strong)));

    font-style: italic;
    cursor:     default;
    opacity:    1;
  }

  /* =========================================================
     LIGHT THEME HARDENING
     =========================================================
     Keep default modal shells visually solid even when the HA
     theme is very light. Custom modal themes can still
     override everything through modal tokens.
     ========================================================= */

  @media (prefers-color-scheme: light) {
    .evcc-modal {
      background:
        var(--evcc-modal-bg,
        #ffffff);

      border:
        1px solid var(--evcc-modal-border,
        rgba(15, 23, 42, 0.12));

      box-shadow:
        var(--evcc-modal-shadow,
        0 20px 60px rgba(0, 0, 0, 0.22));
    }

    .evcc-modal-backdrop {
      background:
        var(--evcc-modal-backdrop-bg,
        rgba(15, 23, 42, 0.28));
    }
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-modal {
      max-height:    calc(100% - 16px);
      border-radius: var(--evcc-modal-radius, 16px);
    }

    .evcc-modal-backdrop {
      padding:     8px;
      align-items: flex-end;
    }
  }
`;var ha=`

  /* =========================================================
     TOKEN BRIDGE
     ========================================================= */

  :host {
    --evcc-learning-panel-bg:
      var(--evcc-surface-panel);

    --evcc-learning-panel-border:
      var(--evcc-border-default);

    --evcc-learning-panel-shadow:
      var(--evcc-shadow-card, 0 6px 14px rgba(0, 0, 0, 0.14));

    --evcc-learning-text-primary:
      var(--evcc-text-primary);

    --evcc-learning-text-secondary:
      var(--evcc-text-secondary);

    --evcc-learning-text-muted:
      var(--evcc-text-muted);

    --evcc-learning-chip-radius:
      var(--evcc-radius-chip, 999px);

    --evcc-learning-chip-font-size: 0.74rem;
    --evcc-learning-chip-font-weight: 700;

    /* === CONFIDENCE: HIGH === */
    --evcc-learning-confidence-high-bg:
      color-mix(in srgb, var(--evcc-sem-success) 18%, transparent);

    --evcc-learning-confidence-high-border:
      color-mix(in srgb, var(--evcc-sem-success) 42%, transparent);

    --evcc-learning-confidence-high-text:
      var(--evcc-sem-success);

    --evcc-learning-confidence-high-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-success) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-success) 10%, transparent)
      );

    /* === CONFIDENCE: MEDIUM === */
    --evcc-learning-confidence-medium-bg:
      color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);

    --evcc-learning-confidence-medium-border:
      color-mix(in srgb, var(--evcc-sem-warning) 42%, transparent);

    --evcc-learning-confidence-medium-text:
      var(--evcc-sem-warning);

    --evcc-learning-confidence-medium-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-warning) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-warning) 10%, transparent)
      );

    /* === CONFIDENCE: LOW === */
    --evcc-learning-confidence-low-bg:
      color-mix(in srgb, var(--evcc-sem-error) 18%, transparent);

    --evcc-learning-confidence-low-border:
      color-mix(in srgb, var(--evcc-sem-error) 42%, transparent);

    --evcc-learning-confidence-low-text:
      var(--evcc-sem-error);

    --evcc-learning-confidence-low-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-sem-error) 26%, transparent),
        color-mix(in srgb, var(--evcc-sem-error) 10%, transparent)
      );

    /* === CONFIDENCE: NEUTRAL / FALLBACK === */
    --evcc-learning-confidence-neutral-bg:
      color-mix(in srgb, var(--evcc-text-muted) 16%, transparent);

    --evcc-learning-confidence-neutral-border:
      var(--evcc-border-default);

    --evcc-learning-confidence-neutral-text:
      var(--evcc-text-secondary);

    --evcc-learning-confidence-neutral-gradient:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-text-muted) 16%, transparent),
        color-mix(in srgb, var(--evcc-text-muted) 8%, transparent)
      );

    /* === SHARED CONFIDENCE TINT TOKENS === */
    --evcc-confidence-high-bg:
      color-mix(in srgb, var(--evcc-sem-success) 18%, transparent);
    --evcc-confidence-high-border:
      color-mix(in srgb, var(--evcc-sem-success) 40%, transparent);
    --evcc-confidence-high-text:
      var(--evcc-sem-success);

    --evcc-confidence-medium-bg:
      color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    --evcc-confidence-medium-border:
      color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    --evcc-confidence-medium-text:
      var(--evcc-sem-warning);

    --evcc-confidence-low-bg:
      color-mix(in srgb, var(--evcc-sem-error) 18%, transparent);
    --evcc-confidence-low-border:
      color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    --evcc-confidence-low-text:
      var(--evcc-sem-error);

    /* === MOTION === */
    --evcc-learning-anim-duration-fast: 180ms;
    --evcc-learning-anim-duration-normal: 260ms;
    --evcc-learning-anim-duration-slow: 520ms;
    --evcc-learning-anim-ease:
      cubic-bezier(0.22, 1, 0.36, 1);

    --evcc-learning-reanchor-highlight:
      color-mix(in srgb, var(--evcc-accent) 16%, transparent);

    --evcc-learning-reanchor-border:
      color-mix(in srgb, var(--evcc-accent) 34%, transparent);

    --evcc-learning-current-glow:
      color-mix(in srgb, var(--evcc-accent) 18%, transparent);
  }

  /* =========================================================
     KEYFRAMES
     ========================================================= */

  @keyframes evccLearningFadeSlideIn {
    0% {
      opacity: 0;
      transform: translateY(8px);
    }
    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes evccLearningBannerPulse {
    0% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-learning-panel-shadow);
    }
    40% {
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--evcc-accent) 16%, transparent),
        var(--evcc-learning-panel-shadow);
    }
    100% {
      box-shadow:
        0 0 0 0 color-mix(in srgb, var(--evcc-accent) 0%, transparent),
        var(--evcc-learning-panel-shadow);
    }
  }

  @keyframes evccLearningRowFlash {
    0% {
      background: color-mix(in srgb, var(--evcc-accent) 0%, transparent);
    }
    35% {
      background: color-mix(in srgb, var(--evcc-accent) 10%, transparent);
    }
    100% {
      background: color-mix(in srgb, var(--evcc-accent) 0%, transparent);
    }
  }

  @keyframes evccLearningCurrentPulse {
    0% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-accent) 12%, transparent);
    }
    70% {
      box-shadow: 0 0 0 6px transparent;
    }
    100% {
      box-shadow: 0 0 0 0 transparent;
    }
  }

  /* =========================================================
     PANEL
     ========================================================= */

  .evcc-learning-panel,
  .evcc-learning-live-banner,
  .evcc-learning-progress {
    display: flex;
    flex-direction: column;
    gap: 12px;

    margin-bottom: 12px;
    padding: 12px 14px;

    border-radius: var(--evcc-radius-panel, 16px);
    border: 1px solid var(--evcc-learning-panel-border);
    background: var(--evcc-learning-panel-bg);
    box-shadow: var(--evcc-learning-panel-shadow);

    color: var(--evcc-learning-text-primary);

    transition:
      border-color var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      box-shadow var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-panel--empty {
    opacity: 0.95;
  }

  .evcc-learning-panel-header,
  .evcc-learning-live-banner {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-learning-panel-title-group,
  .evcc-learning-live-banner-main {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .evcc-learning-panel-title,
  .evcc-learning-live-title,
  .evcc-learning-progress-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--evcc-learning-text-primary);
  }

  .evcc-learning-panel-subtitle,
  .evcc-learning-live-subtitle,
  .evcc-learning-progress-meta,
  .evcc-learning-room-meta,
  .evcc-learning-empty-message {
    font-size: 0.8rem;
    color: var(--evcc-learning-text-secondary);
  }

  /* =========================================================
     ANIMATED SURFACES
     ========================================================= */

  .evcc-learning-live-banner--animated {
    animation:
      evccLearningFadeSlideIn var(--evcc-learning-anim-duration-normal) var(--evcc-learning-anim-ease),
      evccLearningBannerPulse var(--evcc-learning-anim-duration-slow) var(--evcc-learning-anim-ease);
    border-color: var(--evcc-learning-reanchor-border);
    will-change: transform, opacity, box-shadow;
  }

  .evcc-learning-progress-row--animated {
    animation:
      evccLearningFadeSlideIn var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      evccLearningRowFlash var(--evcc-learning-anim-duration-slow) var(--evcc-learning-anim-ease);
    will-change: transform, opacity, background;
  }

  /* =========================================================
     NOTICES
     ========================================================= */

  .evcc-learning-notice {
    display: flex;
    align-items: center;
    gap: 8px;

    padding: 8px 10px;
    border-radius: 10px;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .evcc-learning-notice--stale {
    background: color-mix(in srgb, var(--evcc-sem-warning) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning) 28%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-learning-notice--battery {
    background: color-mix(in srgb, var(--evcc-accent) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent) 28%, transparent);
    color: var(--evcc-accent);
  }

  .evcc-learning-notice--stall {
    background: color-mix(in srgb, var(--evcc-sem-error, #e05) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error, #e05) 30%, transparent);
    color: var(--evcc-sem-error, #e05);
  }

  /* =========================================================
     OVERHEAD
     ========================================================= */

  .evcc-learning-overhead {
    border-top: 1px solid var(--evcc-border-subtle);
    padding-top: 8px;
  }

  .evcc-learning-overhead-summary {
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-learning-text-secondary);
    list-style: none;
  }

  .evcc-learning-overhead-summary::-webkit-details-marker {
    display: none;
  }

  .evcc-learning-overhead-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
  }

  .evcc-learning-overhead-row,
  .evcc-learning-progress-row,
  .evcc-learning-room-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .evcc-learning-overhead-row {
    font-size: 0.8rem;
    color: var(--evcc-learning-text-secondary);
  }

  /* =========================================================
     ROOM LIST / PROGRESS LIST
     ========================================================= */

  .evcc-learning-room-list,
  .evcc-learning-progress-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .evcc-learning-room-row,
  .evcc-learning-progress-row {
    padding: 8px 0;
    border-top: 1px solid var(--evcc-border-subtle);

    transition:
      opacity var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      box-shadow var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-room-main,
  .evcc-learning-progress-main,
  .evcc-learning-progress-side {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .evcc-learning-room-name,
  .evcc-learning-progress-name {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--evcc-learning-text-primary);
    line-height: 1.25;
  }

  .evcc-learning-progress-side {
    align-items: flex-end;
    flex-shrink: 0;
  }

  .evcc-learning-progress-minutes {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-learning-text-secondary);
  }

  .evcc-learning-room-notes {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin-top: 2px;
  }

  .evcc-learning-room-note {
    font-size: 0.74rem;
    color: var(--evcc-learning-text-muted);
  }

  .evcc-learning-progress-row--completed {
    opacity: 0.62;
  }

  .evcc-learning-progress-row--completed .evcc-learning-progress-name {
    text-decoration: line-through;
  }

  .evcc-learning-progress-row--current {
    background:
      linear-gradient(
        90deg,
        color-mix(in srgb, var(--evcc-accent) 10%, transparent),
        transparent
      );
    border-radius: 10px;
    padding: 10px 10px;
    margin: 0 -4px;
    border: 1px solid color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    animation:
      evccLearningCurrentPulse 2.4s ease-in-out infinite;
  }

  /* =========================================================
     CONFIDENCE CHIPS
     ========================================================= */

  .evcc-learning-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 24px;
    padding: 4px 10px;

    border-radius: var(--evcc-learning-chip-radius);
    border: 1px solid var(--evcc-learning-confidence-neutral-border);

    background: var(--evcc-learning-confidence-neutral-gradient);
    color: var(--evcc-learning-confidence-neutral-text);

    font-size: var(--evcc-learning-chip-font-size);
    font-weight: var(--evcc-learning-chip-font-weight);
    line-height: 1;
    white-space: nowrap;

    transition:
      border-color var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      background var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      color var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease),
      transform var(--evcc-learning-anim-duration-fast) var(--evcc-learning-anim-ease);
  }

  .evcc-learning-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-learning-chip--success {
    border-color: var(--evcc-learning-confidence-high-border);
    background: var(--evcc-learning-confidence-high-gradient);
    color: var(--evcc-learning-confidence-high-text);
  }

  .evcc-learning-chip--warning {
    border-color: var(--evcc-learning-confidence-medium-border);
    background: var(--evcc-learning-confidence-medium-gradient);
    color: var(--evcc-learning-confidence-medium-text);
  }

  .evcc-learning-chip--error {
    border-color: var(--evcc-learning-confidence-low-border);
    background: var(--evcc-learning-confidence-low-gradient);
    color: var(--evcc-learning-confidence-low-text);
  }

  .evcc-learning-chip--neutral {
    border-color: var(--evcc-learning-confidence-neutral-border);
    background: var(--evcc-learning-confidence-neutral-gradient);
    color: var(--evcc-learning-confidence-neutral-text);
  }

  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 480px) {
    .evcc-learning-panel,
    .evcc-learning-live-banner,
    .evcc-learning-progress {
      padding: 10px 12px;
      gap: 10px;
    }

    .evcc-learning-panel-header,
    .evcc-learning-live-banner,
    .evcc-learning-room-row,
    .evcc-learning-progress-row {
      flex-direction: column;
      align-items: stretch;
    }

    .evcc-learning-progress-side {
      align-items: flex-start;
    }
  }

  /* =========================================================
     REDUCED MOTION
     ========================================================= */

  @media (prefers-reduced-motion: reduce) {
    .evcc-learning-live-banner--animated,
    .evcc-learning-progress-row--animated,
    .evcc-learning-progress-row--current {
      animation: none !important;
    }

    .evcc-learning-panel,
    .evcc-learning-live-banner,
    .evcc-learning-progress,
    .evcc-learning-room-row,
    .evcc-learning-progress-row,
    .evcc-learning-chip {
      transition: none !important;
    }
  }

  /* =========================================================
     INCOMPLETE RUN BANNER
     =========================================================
     Shown on the Rooms view when the last job was cancelled,
     failed, or interrupted before all rooms were cleaned.
     ========================================================= */

  .evcc-incomplete-run-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 8px 0 4px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-card, 12px);
    background: var(--evcc-surface-warning, rgba(255, 180, 0, 0.12));
    border: 1px solid var(--evcc-border-warning, rgba(255, 180, 0, 0.35));
    font-size: 0.82rem;
  }

  .evcc-incomplete-run-body {
    flex: 1;
    min-width: 0;
  }

  .evcc-incomplete-run-title {
    font-weight: 600;
    color: var(--evcc-text-primary);
    margin-bottom: 4px;
    line-height: 1.3;
  }

  .evcc-incomplete-run-rooms {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }

  .evcc-incomplete-run-room {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--evcc-surface-chip, rgba(255,255,255,0.08));
    border: 1px solid var(--evcc-border-default);
    font-size: 0.76rem;
    font-weight: 500;
    color: var(--evcc-text-secondary);
    white-space: nowrap;
  }

  .evcc-incomplete-run-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .evcc-incomplete-run-retry {
    padding: 5px 12px;
    border-radius: 999px;
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-action, rgba(255,255,255,0.1));
    color: var(--evcc-text-primary);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s ease, opacity 0.15s ease;
  }

  .evcc-incomplete-run-retry:hover {
    background: var(--evcc-surface-action-hover, rgba(255,255,255,0.18));
  }

  .evcc-incomplete-run-retry:active {
    opacity: 0.75;
  }

  .evcc-incomplete-run-dismiss {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 1px solid var(--evcc-border-default);
    background: transparent;
    color: var(--evcc-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s ease, color 0.15s ease;
    padding: 0;
    line-height: 1;
  }

  .evcc-incomplete-run-dismiss:hover {
    background: var(--evcc-surface-chip, rgba(255,255,255,0.1));
    color: var(--evcc-text-primary);
  }

  /* Cleaning Complete summary banner */

  .evcc-learning-summary-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    margin-top: 4px;
  }

  .evcc-learning-summary-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 60px;
  }

  .evcc-learning-summary-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--evcc-text-strong, var(--primary-text-color));
    line-height: 1.1;
  }

  .evcc-learning-summary-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted);
  }

  @media (max-width: 480px) {
    .evcc-learning-summary-stats { gap: 16px; }
    .evcc-learning-summary-stat { min-width: 50px; }
  }
`;var fa=`
  /* =========================================================
     THEME VIEW LAYOUT
     ========================================================= */

  .evcc-view--theme {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    gap: var(--evcc-space-md, 16px);
    min-height: 0;
    overflow: hidden;
  }

  .evcc-view--theme .evcc-view-content {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-space-md, 16px);
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  /* =========================================================
     HEADER
     ========================================================= */

  .evcc-theme-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 4px;
    flex-shrink: 0;
  }

  .evcc-search-box {
    position: relative;
    flex: 1;
    display: flex;
    align-items: center;
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: var(--evcc-radius-inner, 12px);
    padding: 0 12px;
    height: 38px;
    transition: var(--evcc-transition-normal, 150ms ease);
  }

  .evcc-search-box:focus-within {
    border-color: var(--evcc-accent, #3b82f6);
    background: var(--evcc-surface-panel, #1c2127);
  }

  .evcc-search-box ha-icon {
    --mdc-icon-size: 18px;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    margin-right: 8px;
    flex-shrink: 0;
  }

  .evcc-search-box input {
    flex: 1;
    background: none;
    border: none;
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.9rem;
    outline: none;
    width: 100%;
    min-width: 0;
  }

  .evcc-search-box input::placeholder {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
  }

  .evcc-modified-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
  }

  .evcc-theme-tabs {
    margin-bottom: 4px;
    flex-shrink: 0;
  }

  .evcc-theme-filters {
    margin-bottom: 4px;
    flex-shrink: 0;
  }

  /* =========================================================
     PRESETS
     ========================================================= */

  .evcc-preset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 12px;
    padding-bottom: 16px;
  }

  .evcc-preset-card {
    background: var(--evcc-surface-card, #242b33);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 8px;
    cursor: pointer;
    transition: all 200ms ease;
    display: flex;
    flex-direction: column;
    gap: 8px;
    position: relative;
  }

  .evcc-preset-card:hover {
    border-color: var(--evcc-border-strong, rgba(255, 255, 255, 0.2));
    transform: translateY(-2px);
  }

  .evcc-preset-card.active {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(
      in srgb,
      var(--evcc-accent, #3b82f6) 10%,
      var(--evcc-surface-card, #242b33)
    );
  }

  .evcc-preset-delete {
    position: absolute;
    top: 6px;
    right: 6px;
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    cursor: pointer;
    padding: 2px;
  }

  .evcc-preset-preview {
    aspect-ratio: 16 / 9;
    border-radius: var(--evcc-radius-inner, 8px);
    background: var(--evcc-surface-base, #10161f);
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(0, 0, 0, 0.2);
  }

  .preview-swatch {
    position: absolute;
    width: 30%;
    height: 30%;
    border-radius: 50%;
  }

  .preview-swatch.accent {
    background: var(--evcc-accent, #3b82f6);
    top: 20%;
    left: 20%;
  }

  .preview-swatch.surface {
    background: var(--evcc-surface-panel, #1c2127);
    bottom: 20%;
    right: 20%;
  }

  .evcc-preset-label {
    font-size: 0.8rem;
    font-weight: 600;
    text-align: center;
    color: var(--evcc-text-primary, #f0f2f5);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  /* =========================================================
     TOKEN EDITOR GROUPS
     ========================================================= */

  .evcc-token-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }

  .evcc-theme-editor-main {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
  }

  .evcc-theme-editor-main--palette {
    gap: 12px;
  }

  .evcc-theme-editor-scrollbox {
    flex: 1 1 auto;
    height: 0;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
    padding: 12px;
    padding-right: 16px;
    background: color-mix(
      in srgb,
      var(--evcc-surface-panel, #1c2127) 88%,
      transparent
    );
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
  }

  .evcc-token-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-bottom: 20px;
  }

  .evcc-token-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: color-mix(
      in srgb,
      var(--evcc-surface-panel, #1c2127) 82%,
      transparent
    );
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 10px 12px 12px;
  }

  .evcc-token-group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
    user-select: none;
  }

  .group-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
    min-width: 0;
  }

  .group-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .group-toggle {
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    font-size: 0.95rem;
    min-width: 14px;
    text-align: center;
  }

  .evcc-token-group-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .evcc-token-group-search input {
    width: 100%;
    background: var(--evcc-surface-input, rgba(255,255,255,0.05));
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    border-radius: 10px;
    color: var(--evcc-text-primary, #f0f2f5);
    padding: 8px 10px;
    font-size: 0.8rem;
    outline: none;
  }

  .evcc-token-group-search input:focus {
    border-color: var(--evcc-accent, #3b82f6);
  }

  /* Nested sub-groups rendered inside a parent group's body */
  .evcc-token-group--child {
    background: transparent;
    border-color: var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
    border-radius: var(--evcc-radius-card, 12px);
    padding: 8px 10px 10px;
    margin: 0;
  }

  .evcc-token-group--child .group-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  /* =========================================================
     TOKEN ROWS (STACKED DESKTOP MODEL)
     ========================================================= */

  .evcc-token-row {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    background: var(--evcc-surface-panel, #1c2127);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-inner, 12px);
  }

  .evcc-token-row.is-draft {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(
      in srgb,
      var(--evcc-accent, #3b82f6) 4%,
      var(--evcc-surface-panel, #1c2127)
    );
  }

  .token-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .token-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--evcc-text-primary, #f0f2f5);
    min-width: 0;
    flex: 1;
  }

  .token-head-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  /* =========================================================
     TOP STRIP (HEX + RESET + HINT)
     ========================================================= */

  .token-top-strip {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .token-input--hex {
    width: 110px;
    min-width: 110px;
    max-width: 110px;
  }

  .token-hint {
    margin-left: auto;
    font-size: 0.7rem;
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    opacity: 0.8;
    white-space: nowrap;
  }

  /* =========================================================
     TOKEN CONTROL ROWS
     ========================================================= */

  .token-control-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
  }

  .token-control-row--number {
    width: 120px;
  }

  .token-control-row--text {
    width: 100%;
  }

  /* =========================================================
     UNIFIED COLOR CONTROL
     ========================================================= */

  .token-control-row--color {
    width: 100%;
  }

  .token-color-combined-control {
    width: 100%;
    min-width: 0;
  }

  .token-alpha-shell {
    position: relative;
    width: 100%;
    min-width: 0;
    padding-top: 0;
  }

  .token-alpha-rail {
    position: relative;
    width: 100%;
    height: 58px;
    min-width: 0;
    overflow: hidden;
    border-radius: 16px;
    background: var(--evcc-surface-input, rgba(255,255,255,0.05));
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    cursor: ew-resize;
  }

  .token-alpha-rail-fill {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      to right,
      transparent 0%,
      var(--rail-color, var(--evcc-accent, #3b82f6)) 100%
    );
    z-index: 1;
    pointer-events: none;
  }

  .token-alpha-rail-track {
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
  }

  .token-alpha-input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    z-index: 3;
    cursor: ew-resize;
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
  }

  .token-alpha-input::-webkit-slider-runnable-track {
    height: 58px;
    background: transparent;
    border: none;
  }

  .token-alpha-input::-moz-range-track {
    height: 58px;
    background: transparent;
    border: none;
  }

  .token-alpha-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: 21px;
    width: 1px;
    height: 1px;
    opacity: 0;
    border: none;
    box-shadow: none;
    cursor: ew-resize;
  }

  .token-alpha-input::-moz-range-thumb {
    width: 1px;
    height: 1px;
    opacity: 0;
    border: none;
    box-shadow: none;
    cursor: ew-resize;
  }

  .token-alpha-indicator {
    position: absolute;
    top: 6px;
    bottom: 6px;
    width: 2px;
    transform: translateX(-50%);
    background: #ffffff;
    mix-blend-mode: difference;
    opacity: 0.95;
    box-shadow: 0 0 4px rgba(255, 255, 255, 0.35);
    z-index: 4;
    pointer-events: none;
  }

  .hidden-color-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }

  .token-slider-bubble {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    background: var(--evcc-surface-card, #242b33);
    color: var(--evcc-text-primary, #f0f2f5);
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-family: monospace;
    white-space: nowrap;
    pointer-events: none;
  }

  .token-slider-bubble--alpha {
    position: absolute;
    top: -28px;
    transform: translateX(-50%);
    z-index: 5;
    pointer-events: none;
  }

  /* =========================================================
     COLOR-MIX CONTROL
     ========================================================= */

  .token-colormix-colors {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .token-colormix-slot {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
  }

  .token-colormix-swatch {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    flex-shrink: 0;
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
  }

  .token-colormix-color {
    flex: 1;
    min-width: 0;
    font-size: 0.75rem;
  }

  .token-colormix-ratio-label {
    flex-shrink: 0;
    font-size: 0.75rem;
    font-family: monospace;
    color: var(--evcc-text-secondary, rgba(255,255,255,0.7));
    min-width: 36px;
    text-align: center;
  }

  .token-colormix-slider-row {
    position: relative;
    width: 100%;
  }

  .token-colormix-ratio-input {
    width: 100%;
    height: 8px;
    appearance: none;
    -webkit-appearance: none;
    border: none;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    outline: none;
    cursor: pointer;
  }

  .token-colormix-ratio-input::-webkit-slider-runnable-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
  }

  .token-colormix-ratio-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: -4px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    cursor: pointer;
    border: none;
  }

  .token-colormix-ratio-input::-moz-range-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    border: none;
  }

  .token-colormix-ratio-input::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    border: none;
    cursor: pointer;
  }

  .token-colormix-preview {
    width: 100%;
    height: 32px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid var(--evcc-border-default, rgba(255,255,255,0.12));
  }

  /* =========================================================
     NUMERIC CONTROL
     ========================================================= */

  .token-control-row--slider {
    width: 100%;
  }

  .slider-wrap {
    position: relative;
    width: 100%;
    padding-top: 16px;
  }

  .token-input--slider {
    width: 100%;
    height: 8px;
    appearance: none;
    -webkit-appearance: none;
    border: none;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    outline: none;
    cursor: pointer;
  }

  .token-input--slider::-webkit-slider-runnable-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
  }

  .token-input--slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    margin-top: -4px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    cursor: pointer;
    border: none;
  }

  .token-input--slider::-moz-range-track {
    height: 8px;
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--evcc-border-default, rgba(255,255,255,0.12)) 100%,
      transparent
    );
    border: none;
  }

  .token-input--slider::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--evcc-surface-base, #10161f);
    box-shadow:
      0 0 0 2px var(--evcc-accent, #3b82f6),
      0 0 0 4px var(--evcc-surface-base, #10161f);
    border: none;
    cursor: pointer;
  }

  /* =========================================================
     INPUTS
     ========================================================= */

  .token-input {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    padding: 6px 8px;
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.8rem;
    font-family: monospace;
    outline: none;
    min-width: 0;
  }

  .token-input:focus {
    border-color: var(--evcc-accent, #3b82f6);
  }

  .token-input--number {
    width: 100%;
  }

  /* =========================================================
     FOOTER
     ========================================================= */

  .evcc-view-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
    flex-shrink: 0;
  }

  .footer-left,
  .footer-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* =========================================================
     EMPTY STATE
     ========================================================= */

  .evcc-empty {
    color: var(--evcc-text-muted, rgba(255,255,255,0.6));
    padding: 8px 4px;
    font-size: 0.85rem;
  }
`;var ga=`
  /* =========================================================
     THEME PREVIEW PANE
     ========================================================= */

  .evcc-theme-editor-pane {
    display: flex;
    gap: 16px;
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
  }

  .evcc-theme-preview-column {
    display: flex;
    flex: 0 0 320px;
    width: 320px;
    min-height: 0;
    padding-right: 4px;
    overflow: hidden;
  }

  .evcc-theme-preview-pane {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    min-height: 0;
    overflow: hidden;
    padding: 14px;
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, 0 12px 32px rgba(0, 0, 0, 0.25));
  }

  .evcc-theme-preview-header {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-theme-preview-eyebrow {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.55));
  }

  .evcc-theme-preview-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-description {
    font-size: 0.8rem;
    line-height: 1.45;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  .evcc-theme-preview-body,
  .evcc-theme-preview-grid,
  .evcc-theme-preview-text-stack,
  .evcc-theme-preview-border-stack,
  .evcc-theme-preview-shadow-stack,
  .evcc-theme-preview-chip-grid,
  .evcc-theme-preview-status-dots,
  .evcc-theme-preview-queue-strip,
  .evcc-theme-preview-reorder-row,
  .evcc-theme-preview-inline-actions,
  .evcc-theme-preview-modal-body {
    display: flex;
    flex-wrap: wrap;
    gap: var(--evcc-gap, 10px);
  }

  .evcc-theme-preview-body,
  .evcc-theme-preview-grid {
    flex-direction: column;
  }

  .evcc-theme-preview-card,
  .evcc-theme-preview-learning-panel,
  .evcc-theme-preview-room-card {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-gap, 10px);
    padding: var(--evcc-card-padding, 14px);
    min-height: var(--evcc-card-min-height, 0);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, none);
  }

  .evcc-theme-preview-card--hero {
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--evcc-accent, #3b82f6) 14%, transparent),
        transparent 58%
      ),
      var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
  }

  .evcc-theme-preview-section-title,
  .evcc-theme-preview-shell-kicker {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.58));
  }

  .evcc-theme-preview-heading {
    font-family: var(--evcc-font-family, inherit);
    font-size: 1.2rem;
    line-height: 1.15;
    color: var(--evcc-text-primary, #f0f2f5);
    margin: 0;
  }

  .evcc-theme-preview-copy,
  .evcc-theme-preview-text-primary,
  .evcc-theme-preview-modal-title {
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-copy,
  .evcc-theme-preview-text-secondary,
  .evcc-theme-preview-text-muted,
  .evcc-theme-preview-note {
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .evcc-theme-preview-text-secondary,
  .evcc-theme-preview-detail-label {
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
  }

  .evcc-theme-preview-text-muted,
  .evcc-theme-preview-note {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.56));
  }

  .evcc-theme-preview-linkish,
  .evcc-theme-preview-accent-pill {
    color: var(--evcc-accent, #3b82f6);
    font-weight: 600;
  }

  .evcc-theme-preview-accent-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px 10px;
    border-radius: var(--evcc-radius-chip, 999px);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 40%, transparent);
  }

  .evcc-theme-preview-surface-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: var(--evcc-card-padding, 14px);
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    border-radius: var(--evcc-radius-card, 16px);
    box-shadow: var(--evcc-shadow-card, none);
  }

  .evcc-theme-preview-surface-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: var(--evcc-pad, 12px);
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border-radius: var(--evcc-radius-panel, 14px);
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
  }

  .evcc-theme-preview-input {
    display: flex;
    align-items: center;
    min-height: 38px;
    padding: 0 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    background: var(--evcc-surface-input, var(--evcc-bg-input, rgba(255, 255, 255, 0.05)));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.56));
    font-size: 0.82rem;
  }

  .evcc-theme-preview-border-sample,
  .evcc-theme-preview-shadow-sample,
  .evcc-theme-preview-drag-card,
  .evcc-theme-preview-order-target {
    padding: 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    background: var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
    color: var(--evcc-text-primary, #f0f2f5);
    font-size: 0.82rem;
  }

  .evcc-theme-preview-border-sample--subtle {
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
  }

  .evcc-theme-preview-border-sample--default {
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
  }

  .evcc-theme-preview-border-sample--strong {
    border: 1px solid var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
  }

  .evcc-theme-preview-shadow-sample--card {
    box-shadow: var(--evcc-shadow-card, 0 8px 20px rgba(0, 0, 0, 0.2));
  }

  .evcc-theme-preview-shadow-sample--hover {
    box-shadow: var(--evcc-shadow-hover, 0 12px 30px rgba(0, 0, 0, 0.28));
    transform: translateY(calc(var(--evcc-hover-lift, 0px) * -1));
  }

  .evcc-theme-preview-chip-grid .evcc-chip {
    cursor: default;
  }

  .evcc-theme-preview-chip--hover {
    background: var(--evcc-chip-hover-bg, var(--evcc-chip-bg, rgba(255, 255, 255, 0.05)));
    border-color: var(--evcc-chip-hover-border, var(--evcc-chip-border, rgba(255, 255, 255, 0.12)));
    color: var(--evcc-chip-hover-text, var(--evcc-chip-text, #f0f2f5));
  }

  .evcc-theme-preview-chip--included {
    background: var(--evcc-chip-included-bg, rgba(34, 197, 94, 0.15));
    border-color: var(--evcc-chip-included-border, rgba(34, 197, 94, 0.3));
    color: var(--evcc-chip-included-text, #22c55e);
  }

  .evcc-theme-preview-chip--excluded {
    background: var(--evcc-chip-excluded-bg, rgba(239, 68, 68, 0.12));
    border-color: var(--evcc-chip-excluded-border, rgba(239, 68, 68, 0.3));
    color: var(--evcc-chip-excluded-text, #f87171);
  }

  .evcc-theme-preview-chip--success {
    background: var(--evcc-chip-success-bg, rgba(34, 197, 94, 0.15));
    border-color: var(--evcc-chip-success-border, rgba(34, 197, 94, 0.3));
    color: var(--evcc-chip-success-text, #22c55e);
  }

  .evcc-theme-preview-chip--warning {
    background: var(--evcc-chip-warning-bg, rgba(245, 158, 11, 0.15));
    border-color: var(--evcc-chip-warning-border, rgba(245, 158, 11, 0.35));
    color: var(--evcc-chip-warning-text, #f59e0b);
  }

  .evcc-theme-preview-room-card {
    position: relative;
    overflow: hidden;
    background:
      linear-gradient(
        90deg,
        color-mix(in srgb, var(--evcc-accent, #3b82f6) var(--evcc-room-fill-opacity, 10%), transparent),
        transparent 70%
      ),
      var(--evcc-surface-card, var(--evcc-card-bg, #242b33));
  }

  .evcc-theme-preview-room-card--filled::before {
    content: "";
    position: absolute;
    inset: 0;
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) var(--evcc-room-fill-opacity, 18%), transparent);
    pointer-events: none;
  }

  .evcc-theme-preview-room-header,
  .evcc-theme-preview-room-detail-row,
  .evcc-theme-preview-modal-header,
  .evcc-theme-preview-modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .evcc-theme-preview-room-name,
  .evcc-theme-preview-surface-title {
    font-weight: 700;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-preview-profile-chip {
    background: var(--evcc-profile-chip-bg, rgba(255, 255, 255, 0.06));
    border-color: var(--evcc-profile-chip-border, rgba(255, 255, 255, 0.14));
    color: var(--evcc-profile-chip-text, var(--evcc-text-primary, #f0f2f5));
  }

  .evcc-theme-preview-profile-chip--custom {
    background: var(--evcc-profile-chip-custom-bg, rgba(245, 158, 11, 0.14));
    border-color: var(--evcc-profile-chip-custom-border, rgba(245, 158, 11, 0.3));
    color: var(--evcc-profile-chip-custom-text, #f59e0b);
  }

  .evcc-theme-preview-room-chip {
    background: var(--evcc-room-chip-bg, rgba(255, 255, 255, 0.06));
    border-color: var(--evcc-room-chip-border, rgba(255, 255, 255, 0.14));
    color: var(--evcc-room-chip-text, var(--evcc-text-secondary, rgba(255, 255, 255, 0.72)));
  }

  /* =========================================================
     FLOOR TEXTURE PREVIEW \u2014 real room-card grid
     ========================================================= */

  .evcc-theme-preview-ftx-card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--evcc-gap, 10px);
    pointer-events: none;
  }

  .evcc-theme-preview-order-chip,
  .evcc-theme-preview-room-order {
    background: var(--evcc-order-chip-bg, var(--evcc-queue-order-bg, rgba(255, 255, 255, 0.06)));
    border-color: var(--evcc-order-chip-border, var(--evcc-queue-order-border, rgba(255, 255, 255, 0.14)));
    color: var(--evcc-order-chip-text, var(--evcc-queue-order-text, var(--evcc-text-primary, #f0f2f5)));
  }

  .evcc-theme-preview-queue-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--evcc-queue-chip-gap, 8px);
    padding: 8px 10px;
    border-radius: var(--evcc-radius-chip, 999px);
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    font-size: 0.82rem;
    white-space: nowrap;
  }

  .evcc-theme-preview-queue-chip--current {
    background: var(--evcc-queue-current-bg, rgba(59, 130, 246, 0.12));
    border-color: var(--evcc-queue-current-border, rgba(59, 130, 246, 0.28));
    color: var(--evcc-queue-current-text, var(--evcc-text-primary, #f0f2f5));
    box-shadow: var(--evcc-queue-current-glow, none);
  }

  .evcc-theme-preview-queue-chip--pending {
    background: var(--evcc-queue-pending-bg, rgba(255, 255, 255, 0.05));
    border-color: var(--evcc-queue-pending-border, rgba(255, 255, 255, 0.12));
    color: var(--evcc-queue-pending-text, var(--evcc-text-secondary, rgba(255, 255, 255, 0.72)));
    opacity: var(--evcc-queue-pending-opacity, 1);
  }

  .evcc-theme-preview-queue-chip--completed {
    background: var(--evcc-queue-completed-bg, rgba(34, 197, 94, 0.12));
    border-color: var(--evcc-queue-completed-border, rgba(34, 197, 94, 0.28));
    color: var(--evcc-queue-completed-text, #22c55e);
    opacity: var(--evcc-queue-completed-opacity, 1);
  }

  .evcc-theme-preview-queue-chip--inferred {
    background: var(--evcc-queue-inferred-bg, rgba(245, 158, 11, 0.12));
    border-color: var(--evcc-queue-inferred-border, rgba(245, 158, 11, 0.28));
    color: var(--evcc-queue-inferred-text, #f59e0b);
    box-shadow: var(--evcc-queue-inferred-glow, none);
  }

  .evcc-theme-preview-drag-card {
    opacity: var(--evcc-drag-opacity, 0.88);
    transform: scale(var(--evcc-drag-scale, 1.02));
    box-shadow: var(--evcc-drag-shadow, var(--evcc-shadow-hover, 0 12px 30px rgba(0, 0, 0, 0.28)));
  }

  .evcc-theme-preview-order-target {
    border: 1px dashed var(--evcc-order-target-outline, var(--evcc-order-feedback-border, rgba(59, 130, 246, 0.35)));
    background: transparent;
  }

  .evcc-theme-preview-status-dot {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.72));
    font-size: 0.82rem;
  }

  .evcc-theme-preview-status-dot::before {
    content: "";
    width: 10px;
    height: 10px;
    border-radius: 50%;
    box-shadow: var(--evcc-status-dot-shadow, none);
    animation: evcc-theme-preview-pulse var(--evcc-status-pulse-duration, 1600ms) ease-in-out infinite;
  }

  .evcc-theme-preview-status-dot--idle::before {
    background: var(--evcc-status-dot-idle, var(--evcc-color-idle, #94a3b8));
  }

  .evcc-theme-preview-status-dot--cleaning::before {
    background: var(--evcc-status-dot-cleaning, var(--evcc-color-cleaning, #3b82f6));
  }

  .evcc-theme-preview-status-dot--docked::before {
    background: var(--evcc-status-dot-docked, var(--evcc-color-docked, #22c55e));
  }

  .evcc-theme-preview-status-dot--error::before {
    background: var(--evcc-status-dot-error, var(--evcc-color-error, #ef4444));
  }

  .evcc-theme-preview-confidence-high,
  .evcc-theme-preview-learning-confidence-high {
    background: var(--evcc-confidence-high-bg, var(--evcc-learning-confidence-high-bg, rgba(34, 197, 94, 0.12)));
    border-color: var(--evcc-confidence-high-border, var(--evcc-learning-confidence-high-border, rgba(34, 197, 94, 0.28)));
    color: var(--evcc-confidence-high-text, var(--evcc-learning-confidence-high-text, #22c55e));
  }

  .evcc-theme-preview-confidence-medium,
  .evcc-theme-preview-learning-confidence-medium {
    background: var(--evcc-confidence-medium-bg, var(--evcc-learning-confidence-medium-bg, rgba(245, 158, 11, 0.12)));
    border-color: var(--evcc-confidence-medium-border, var(--evcc-learning-confidence-medium-border, rgba(245, 158, 11, 0.28)));
    color: var(--evcc-confidence-medium-text, var(--evcc-learning-confidence-medium-text, #f59e0b));
  }

  .evcc-theme-preview-confidence-low {
    background: var(--evcc-confidence-low-bg, rgba(239, 68, 68, 0.12));
    border-color: var(--evcc-confidence-low-border, rgba(239, 68, 68, 0.28));
    color: var(--evcc-confidence-low-text, #f87171);
  }

  .evcc-theme-preview-alert {
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 12px);
    border: 1px solid transparent;
    font-size: 0.8rem;
  }

  .evcc-theme-preview-alert--info {
    background: color-mix(in srgb, var(--evcc-sem-info, #3b82f6) 12%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-info, #3b82f6) 28%, transparent);
    color: var(--evcc-sem-info, #3b82f6);
  }

  .evcc-theme-preview-alert--warning {
    background: var(--evcc-modal-warning-bg, color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 12%, transparent));
    border-color: var(--evcc-modal-warning-border, color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 28%, transparent));
    color: var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b));
  }

  .evcc-theme-preview-alert--error {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 28%, transparent);
    color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-theme-preview-estimate-default {
    background: var(--evcc-estimate-default-bg, rgba(148, 163, 184, 0.12));
    border-color: var(--evcc-estimate-default-border, rgba(148, 163, 184, 0.28));
    color: var(--evcc-estimate-default-text, #cbd5e1);
  }

  .evcc-theme-preview-estimate-learned {
    background: var(--evcc-estimate-learned-bg, rgba(59, 130, 246, 0.12));
    border-color: var(--evcc-estimate-learned-border, rgba(59, 130, 246, 0.28));
    color: var(--evcc-estimate-learned-text, #60a5fa);
  }

  .evcc-theme-preview-learning-panel {
    background:
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--evcc-learning-reanchor-highlight, var(--evcc-accent, #3b82f6)) 12%, transparent),
        transparent 62%
      ),
      var(--evcc-learning-panel-bg, var(--evcc-surface-panel, #1c2127));
    border-color: var(--evcc-learning-panel-border, var(--evcc-border-default, rgba(255, 255, 255, 0.12)));
    box-shadow: var(--evcc-learning-panel-shadow, none);
  }

  .evcc-theme-preview-note {
    color: var(--evcc-learning-note-text, var(--evcc-learning-text-secondary, rgba(255, 255, 255, 0.72)));
  }

  .evcc-theme-preview-modal-stage {
    position: relative;
    min-height: 260px;
    overflow: hidden;
    border-radius: var(--evcc-radius-card, 16px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
  }

  .evcc-theme-preview-modal-backdrop {
    position: absolute;
    inset: 0;
    background: var(--evcc-modal-backdrop-bg, rgba(0, 0, 0, 0.7));
    backdrop-filter: blur(calc(var(--evcc-modal-backdrop-blur, 8) * 1px));
  }

  .evcc-theme-preview-modal {
    position: relative;
    z-index: 1;
    width: min(92%, 320px);
    margin: 18px auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: var(--evcc-modal-padding, 16px);
    background: var(--evcc-modal-bg, #1c2127);
    border: 1px solid var(--evcc-modal-border, rgba(255, 255, 255, 0.14));
    border-radius: var(--evcc-modal-radius, 18px);
    box-shadow: var(--evcc-modal-shadow, 0 20px 60px rgba(0, 0, 0, 0.6));
  }

  .evcc-theme-preview-modal-title {
    font-size: 0.96rem;
    font-weight: 700;
  }

  .evcc-theme-preview-modal-accent-chip {
    background: var(--evcc-modal-accent-bg, color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)) 18%, transparent));
    border-color: var(--evcc-modal-accent-border, color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)) 36%, transparent));
    color: var(--evcc-modal-accent-text, var(--evcc-modal-accent, var(--evcc-accent, #3b82f6)));
  }

  .evcc-theme-preview-foundation-card {
    gap: var(--evcc-section-gap, 16px);
  }

  @keyframes evcc-theme-preview-pulse {
    0%, 100% {
      opacity: 0.85;
    }

    50% {
      opacity: 1;
    }
  }

  @media (max-width: 1100px) {
    .evcc-theme-editor-pane {
      flex-direction: column;
    }

    .evcc-theme-preview-column {
      flex: 0 0 auto;
      width: 100%;
      overflow: visible;
      order: -1;
      padding-right: 0;
    }

    .evcc-theme-preview-pane {
      max-height: none;
      overflow: visible;
    }
  }
`;var _a=`

  /* =========================================================
     VIEW TOGGLE STRIP
     ========================================================= */

  .evcc-rooms-view-toggle {
    display:     flex;
    gap:         4px;
    margin-left: auto;
    flex-shrink: 0;
  }

  .evcc-rooms-view-toggle-btn {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           32px;
    height:          32px;
    padding:         0;
    border-radius:   8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:      transparent;
    color:
      var(--evcc-text-muted,
      rgba(240, 242, 245, 0.48));
    cursor:          pointer;
    transition:      background 150ms ease,
                     color 150ms ease,
                     border-color 150ms ease;
  }

  .evcc-rooms-view-toggle-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:
      var(--evcc-text-secondary,
      rgba(240, 242, 245, 0.72));
  }

  .evcc-rooms-view-toggle-btn.active {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:       var(--evcc-text-primary, #f0f2f5);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  /* =========================================================
     MAP VIEW CONTAINER
     ========================================================= */

  .evcc-map-view {
    display:        flex;
    flex-direction: column;
    flex:           1;
    min-height:     0;
  }

  .evcc-map-container {
    position:      relative;
    width:         100%;
    aspect-ratio:  1;
    min-height:    240px;
    overflow:      hidden;
    border-radius: var(--evcc-radius-card, 12px);
    background:    var(--evcc-surface-panel, #1c2127);
    isolation:     isolate;
  }

  .evcc-map-layers {
    position:         absolute;
    inset:            0;
    transform-origin: 0 0;
    will-change:      transform;
  }

  .evcc-map-image {
    display:            block;
    width:              100%;
    height:             100%;
    object-fit:         contain;
    user-select:        none;
    -webkit-user-drag:  none;
  }

  .evcc-map-svg {
    position:       absolute;
    inset:          0;
    width:          100%;
    height:         100%;
    pointer-events: none;
  }

  .evcc-map-debug-origin {
    fill:           red;
    stroke:         white;
    stroke-width:   0.3;
    pointer-events: none;
  }

  /* =========================================================
     ANIMAL SVG COMPANION
     =========================================================
     Positioned absolutely in .evcc-map-layers (same space as
     the labels and old presence dot).  The inner <animal-svg>
     handles its own shadow DOM; we just control the host box.
     ========================================================= */

  .evcc-map-animal {
    position:       absolute;
    /* width + height set inline by renderer (respects user scale) */
    transform:      translate(-50%, -50%);
    cursor:         grab;
    z-index:        10;
    pointer-events: all;
    touch-action:   none;   /* prevent scroll takeover during drag on touch */
    /* Drop shadow so the animal reads on any map colour */
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.65));
    transition:     filter 400ms ease, opacity 400ms ease;
  }

  /* Actively being dragged */
  .evcc-map-animal--dragging {
    cursor:     grabbing;
    transition: none;   /* suppress filter transition while moving */
  }

  /* Docked / charging \u2014 gentle luminance + alpha breath pulse */
  .evcc-map-animal--pulse {
    animation: evcc-animal-pulse 3.5s ease-in-out infinite;
  }

  @keyframes evcc-animal-pulse {
    0%, 100% {
      filter: drop-shadow(0 2px 6px rgba(0,0,0,0.65))
              brightness(0.75) opacity(0.65);
    }
    45% {
      filter: drop-shadow(0 2px 8px rgba(0,0,0,0.55))
              brightness(1.05) opacity(1);
    }
  }

  /* =========================================================
     POLYGONS
     ========================================================= */

  .evcc-map-polygon {
    fill:           transparent;
    stroke:         none;
    cursor:         pointer;
    pointer-events: all;
    transition:     fill-opacity 150ms ease;
  }

  .evcc-map-polygon--selected {
    fill:         var(--seg-color);
    fill-opacity: 0.25;
  }

  /* =========================================================
     MAP LABELS (centroid overlays)
     ========================================================= */

  .evcc-map-label {
    position:       absolute;
    transform:      translate(-50%, -50%);
    display:        flex;
    flex-direction: column;
    align-items:    center;
    gap:            3px;
    pointer-events: none;
    z-index:        5;
  }

  .evcc-map-label-name {
    font-size:   0.82rem;
    font-weight: 700;
    color:       rgba(240, 242, 245, 0.90);
    text-shadow: 0 1px 4px rgba(0,0,0,0.90), 0 0 8px rgba(0,0,0,0.65);
    white-space: nowrap;
    line-height: 1.2;
    text-align:  center;
  }

  .evcc-map-label--selected .evcc-map-label-name {
    color: #ffffff;
  }

  .evcc-map-label-order {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           16px;
    height:          16px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           #fff;
    font-size:       0.58rem;
    font-weight:     700;
    line-height:     1;
    box-shadow:      0 1px 4px rgba(0, 0, 0, 0.55);
  }

  /* =========================================================
     MAP TOOLTIP
     ========================================================= */

  .evcc-map-tooltip {
    position:       absolute;
    display:        none;
    flex-direction: column;
    gap:            2px;
    padding:        6px 10px;
    background:     rgba(15, 18, 22, 0.88);
    backdrop-filter: blur(6px);
    border:         1px solid rgba(255, 255, 255, 0.12);
    border-radius:  8px;
    pointer-events: none;
    max-width:      180px;
    z-index:        10;
  }

  .evcc-map-tooltip--visible {
    display: flex;
  }

  .evcc-map-tooltip-label {
    font-size:   0.82rem;
    font-weight: 600;
    color:       #f0f2f5;
    white-space: nowrap;
  }

  .evcc-map-tooltip-hint {
    font-size: 0.72rem;
    color:     rgba(240, 242, 245, 0.55);
    white-space: nowrap;
  }

  /* =========================================================
     UNAVAILABLE STATE
     ========================================================= */

  .evcc-map-unavailable {
    display:         flex;
    flex-direction:  column;
    align-items:     center;
    justify-content: center;
    gap:             8px;
    padding:         32px 20px;
    color:
      var(--evcc-text-secondary,
      rgba(240, 242, 245, 0.72));
    font-size:       0.88rem;
    text-align:      center;
  }

  .evcc-map-unavailable-hint {
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size: 0.80rem;
  }

  /* =========================================================
     SELECTION BAR
     ========================================================= */

  .evcc-map-selection-bar {
    display:     flex;
    flex-wrap:   wrap;
    gap:         8px;
    padding:     10px 12px;
    background:  var(--evcc-surface-panel, #1c2127);
    border-top:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
    flex-shrink: 0;
  }

  .evcc-map-chip {
    display:        flex;
    flex-direction: row;
    align-items:    center;
    gap:            8px;
    padding:        6px 12px;
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    border-radius: 8px;
    cursor:        pointer;
    user-select:   none;
    min-width:     68px;
    transition:    background 150ms ease, border-color 150ms ease;
    touch-action:  none;
  }

  .evcc-map-chip:hover {
    background:
      var(--evcc-surface-panel, #1c2127);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  .evcc-map-chip-order {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           18px;
    height:          18px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           #fff;
    font-size:       0.68rem;
    font-weight:     700;
    flex-shrink:     0;
    line-height:     1;
  }

  .evcc-map-chip-body {
    display:        flex;
    flex-direction: column;
    gap:            2px;
    min-width:      0;
  }

  .evcc-map-chip-label {
    font-size:     0.82rem;
    font-weight:   600;
    color:         var(--evcc-text-primary, #f0f2f5);
    white-space:   nowrap;
    overflow:      hidden;
    text-overflow: ellipsis;
  }

  .evcc-map-chip-settings {
    font-size:   0.74rem;
    color:       var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    white-space: nowrap;
  }

  /* =========================================================
     MAP CONFIG VIEW
     ========================================================= */

  .evcc-map-config-view {
    display:        flex;
    flex-direction: column;
    flex:           1;
    min-height:     0;
    gap:            0;
  }

  .evcc-map-config-body {
    display:    flex;
    flex:       1;
    min-height: 0;
  }

  .evcc-map-config-side-panel {
    display:        flex;
    flex-direction: column;
    width:          220px;
    flex-shrink:    0;
    overflow-y:     auto;
    border-left:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-header {
    display:         flex;
    align-items:     center;
    gap:             12px;
    padding:         10px 12px 8px;
    flex-shrink:     0;
    border-bottom:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-back {
    display:      flex;
    align-items:  center;
    gap:          6px;
    padding:      4px 10px 4px 6px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:   transparent;
    color:        var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:    0.82rem;
    cursor:       pointer;
    transition:   background 150ms ease, color 150ms ease;
  }

  .evcc-map-config-back:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-config-title {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-polygon--config {
    cursor:         pointer;
    pointer-events: all;
    transition:     filter 120ms ease;
  }

  .evcc-map-polygon--config:hover {
    filter: brightness(1.35);
  }

  .evcc-map-vertex-dot {
    transition: r 120ms ease, filter 120ms ease;
  }

  .evcc-map-vertex-dot:hover {
    filter: brightness(1.4);
  }

  .evcc-map-vertex-dot--selected {
    filter: drop-shadow(0 0 1px rgba(255, 221, 0, 0.9));
  }

  /* =========================================================
     CONFIG PANEL
     ========================================================= */

  .evcc-map-config-panel {
    display:        flex;
    flex-direction: column;
    gap:            0;
    flex-shrink:    0;
    border-top:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-config-section {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 12px;
    border-bottom:
      1px solid var(--evcc-border-subtle,
      rgba(255, 255, 255, 0.06));
  }

  .evcc-map-config-section--hint {
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size: 0.82rem;
    align-items: center;
    padding: 12px;
  }

  .evcc-map-config-section-title {
    font-size:      0.72rem;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-section-title em {
    font-style:     normal;
    font-weight:    700;
    color:          var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    text-transform: none;
    letter-spacing: normal;
  }

  /* =========================================================
     VARIANT ROWS
     ========================================================= */

  .evcc-map-variant-row {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-map-variant-info {
    display:        flex;
    flex-direction: column;
    gap:            1px;
    flex:           1;
    min-width:      0;
  }

  .evcc-map-variant-label {
    font-size:  0.82rem;
    font-weight: 600;
    color:      var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-variant-hint {
    font-size: 0.72rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  .evcc-map-variant-status {
    font-size:   0.74rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .evcc-map-variant-status--ok {
    color: var(--evcc-sem-success, #22c55e);
  }

  .evcc-map-variant-status--missing {
    color: var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-analyze-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             8px;
    padding-top:     4px;
  }

  .evcc-map-config-seg-count {
    font-size: 0.80rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-map-config-btn {
    padding:       5px 12px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.80rem;
    cursor:        pointer;
    white-space:   nowrap;
    flex-shrink:   0;
    transition:    background 150ms ease, color 150ms ease;
  }

  .evcc-map-config-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-map-config-btn--primary {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 18%, transparent);
    color:
      var(--evcc-accent, #3b82f6);
    border-color:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 40%, transparent);
    font-weight: 600;
  }

  .evcc-map-config-btn--primary:hover {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 28%, transparent);
    color: var(--evcc-accent, #3b82f6);
  }

  .evcc-map-config-btn:disabled,
  .evcc-map-config-btn--busy {
    opacity: 0.55;
    cursor:  default;
  }

  .evcc-map-action-status {
    font-size:   0.74rem;
    font-weight: 500;
    flex-shrink: 0;
  }

  .evcc-map-action-status--error {
    color: var(--evcc-sem-error, #ef4444);
  }

  /* =========================================================
     NUDGE PAD
     ========================================================= */

  .evcc-map-nudge-pad {
    display:        flex;
    flex-direction: column;
    align-items:    center;
    gap:            4px;
    align-self:     flex-start;
  }

  .evcc-map-nudge-row {
    display: flex;
    gap:     4px;
  }

  .evcc-map-nudge-btn {
    width:         36px;
    height:        36px;
    display:       flex;
    align-items:   center;
    justify-content: center;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     1rem;
    cursor:        pointer;
    transition:    background 120ms ease;
  }

  .evcc-map-nudge-btn:hover {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.08));
  }

  .evcc-map-nudge-btn:active {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.14));
  }

  .evcc-map-nudge-btn--reset {
    color:        var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    border-color: transparent;
    font-size:    0.9rem;
  }

  .evcc-map-config-adj-meta {
    font-size: 0.74rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  /* =========================================================
     EDGE ADJUST
     ========================================================= */

  .evcc-map-edge-grid {
    display:        flex;
    flex-direction: column;
    gap:            4px;
  }

  .evcc-map-edge-row {
    display:     flex;
    align-items: center;
    gap:         4px;
  }

  .evcc-map-edge-label {
    font-size:  0.72rem;
    color:      var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    width:      44px;
    flex-shrink: 0;
  }

  .evcc-map-edge-val {
    font-size:   0.72rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    min-width:   28px;
    text-align:  center;
    flex-shrink: 0;
  }

  .evcc-map-nudge-btn--edge {
    width:     28px;
    height:    28px;
    font-size: 1rem;
    flex-shrink: 0;
  }

  /* =========================================================
     VERTEX ADJUST
     ========================================================= */

  .evcc-map-vertex-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       4px;
  }

  .evcc-map-vertex-chip {
    min-width:     24px;
    height:        24px;
    padding:       0 6px;
    border-radius: 6px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-size:     0.70rem;
    cursor:        pointer;
    transition:    background 120ms ease, color 120ms ease, border-color 120ms ease;
  }

  .evcc-map-vertex-chip:hover {
    background:
      var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color: var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
  }

  .evcc-map-vertex-chip--selected {
    background:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 20%, transparent);
    color:        var(--evcc-accent, #3b82f6);
    border-color:
      color-mix(in srgb, var(--evcc-accent, #3b82f6) 45%, transparent);
    font-weight:  600;
  }

  .evcc-map-vertex-chip--adjusted {
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 40%, transparent);
  }

  .evcc-map-vertex-chip--selected.evcc-map-vertex-chip--adjusted {
    background:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 20%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 45%, transparent);
  }

  /* =========================================================
     ROOM ASSIGNMENT CHIPS
     ========================================================= */

  .evcc-map-room-assign-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       6px;
  }

  .evcc-map-room-assign-chip {
    padding:       5px 12px;
    border-radius: 8px;
    border:
      1px solid var(--evcc-border-default,
      rgba(255, 255, 255, 0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.80rem;
    cursor:        pointer;
    transition:    background 120ms ease, color 120ms ease, border-color 120ms ease;
  }

  .evcc-map-room-assign-chip:hover:not(:disabled) {
    background:
      var(--evcc-surface-input,
      rgba(255, 255, 255, 0.06));
    color:        var(--evcc-text-primary, #f0f2f5);
    border-color:
      var(--evcc-border-strong,
      rgba(255, 255, 255, 0.18));
  }

  .evcc-map-room-assign-chip--linked {
    background:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 16%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
    border-color:
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 38%, transparent);
    font-weight:  600;
  }

  .evcc-map-room-assign-chip--taken {
    opacity: 0.35;
    cursor:  default;
  }

  /* =========================================================
     CONFIGURE BUTTON IN INLINE MAP VIEW
     ========================================================= */

  .evcc-rooms-view-toggle-btn--configure {
    width:  auto;
    padding: 0 10px;
    gap:    6px;
    font-size: 0.76rem;
  }

  /* =========================================================
     ANIMAL SELECTOR IN MAP TOOLBAR
     ========================================================= */

  .evcc-rooms-animal-select {
    height:        32px;
    padding:       0 6px;
    border-radius: 8px;
    border:        1px solid var(--evcc-border-default, rgba(255,255,255,0.10));
    background:    transparent;
    color:         var(--evcc-text-secondary, rgba(240,242,245,0.72));
    font-size:     0.76rem;
    cursor:        pointer;
    outline:       none;
    flex-shrink:   0;
    /* Native <select> appearance for simplicity \u2014 themed via border/bg */
    -webkit-appearance: auto;
    appearance:    auto;
  }

  .evcc-rooms-animal-select:hover {
    border-color: var(--evcc-border-strong, rgba(255,255,255,0.18));
    color:        var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-rooms-animal-select option {
    background: var(--evcc-surface-panel, #1c2127);
    color:      var(--evcc-text-primary, #f0f2f5);
  }

  /* =========================================================
     ANIMAL SCALE SLIDER
     ========================================================= */

  .evcc-rooms-animal-scale {
    width:       72px;
    height:      32px;
    flex-shrink: 0;
    cursor:      pointer;
    accent-color: var(--evcc-accent, #6366f1);
    /* keep the range input vertically centred in the toolbar row */
    align-self:  center;
  }
`;var ba=`

  /* =========================================================
     CARD TEXTURE CONTAINER
     ========================================================= */

  .evcc-room-texture-layer {
    position:       absolute;
    inset:          0;
    pointer-events: none;
    z-index:        0;
  }

  /* Higher-specificity override: rooms.js sets
     .evcc-room-card > * { position:relative; z-index:1 }
     which would lift the texture layer above z-index:0.
     Re-declare here so the texture stays behind content. */
  .evcc-room-card > .evcc-room-texture-layer {
    position: absolute;
    z-index:  0;
    inset:    0;
  }

  /* =========================================================
     MASK LAYER SPANS
     ========================================================= */

  .evcc-ftx-layer {
    display:                block;
    position:               absolute;
    inset:                  0;
    mask-repeat:            no-repeat;
    mask-size:              cover;
    mask-position:          var(--floor-position-card, center);
    mask-mode:              luminance;
    -webkit-mask-repeat:    no-repeat;
    -webkit-mask-size:      cover;
    -webkit-mask-position:  var(--floor-position-card, center);
    -webkit-mask-mode:      luminance;
    opacity: calc(
      var(--evcc-floor-textures-card-enabled, 1) *
      var(--floor-opacity-card, 0.85) *
      var(--layer-opacity, 1)
    );
  }

  /* =========================================================
     MAP TEXTURE OVERLAY POLYGON
     ========================================================= */

  .evcc-map-texture-polygon {
    pointer-events: none;
    opacity: calc(
      var(--evcc-floor-texture-opacity-map,  0.15) *
      var(--evcc-floor-textures-map-enabled, 1)
    );
  }
`;var ya=`
  /* =========================================================
     SETUP VIEW
     ========================================================= */

  .evcc-setup-view {
    padding:        20px;
    display:        flex;
    flex-direction: column;
    gap:            16px;
  }

  .evcc-setup-header {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    margin-bottom:  4px;
  }

  .evcc-setup-title {
    font-size:   1.05rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-description {
    font-size:   0.86rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.5;
  }

  /* =========================================================
     STEP CARD
     ========================================================= */

  .evcc-setup-step {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-step-header {
    display:     flex;
    align-items: center;
    gap:         10px;
  }

  .evcc-setup-step-badge {
    width:           24px;
    height:          24px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           #fff;
    display:         flex;
    align-items:     center;
    justify-content: center;
    font-size:       0.76rem;
    font-weight:     700;
    flex-shrink:     0;
    transition:      background 200ms ease;
  }

  .evcc-setup-step-badge.done {
    background: var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-step-label {
    font-size:   0.92rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-step-body {
    font-size:   0.84rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.45;
  }

  .evcc-setup-step-body.muted {
    opacity: 0.5;
  }

  .evcc-setup-entity-id {
    font-family:    monospace;
    font-size:      0.80rem;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    margin-top:     4px;
    word-break:     break-all;
  }

  /* =========================================================
     BUTTONS
     ========================================================= */

  .evcc-setup-btn {
    align-self:    flex-start;
    padding:       8px 18px;
    border-radius: 8px;
    background:    var(--evcc-accent, #3b82f6);
    color:         #fff;
    font-size:     0.86rem;
    font-weight:   600;
    border:        none;
    cursor:        pointer;
    transition:    opacity 150ms ease;
    line-height:   1;
  }

  .evcc-setup-btn:hover:not(:disabled) {
    opacity: 0.85;
  }

  .evcc-setup-btn:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  .evcc-setup-btn.secondary {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.08));
    color:      var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    border:     1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  /* =========================================================
     RESULT BANNERS
     ========================================================= */

  .evcc-setup-result {
    padding:       9px 13px;
    border-radius: 8px;
    font-size:     0.84rem;
    font-weight:   500;
    line-height:   1.4;
  }

  .evcc-setup-result.success {
    background:   color-mix(in srgb, var(--evcc-sem-success, #22c55e) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-success, #22c55e) 32%, transparent);
    color:        var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-result.error {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 32%, transparent);
    color:        var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-result.info {
    background:   color-mix(in srgb, var(--evcc-accent, #3b82f6) 14%, transparent);
    border:       1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 32%, transparent);
    color:        var(--evcc-accent, #3b82f6);
  }

  /* =========================================================
     READY STATE \u2014 ROOM SUMMARY
     ========================================================= */

  .evcc-setup-vacuum-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-vacuum-entry {
    display:        flex;
    flex-direction: column;
    gap:            4px;
    padding:        10px 12px;
    border-radius:  8px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border:         1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.07));
  }

  .evcc-setup-vacuum-name {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-vacuum-meta {
    font-size: 0.80rem;
    color:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  /* =========================================================
     IMPORTED MAPS LIST
     ========================================================= */

  .evcc-setup-map-list {
    display:        flex;
    flex-direction: column;
    gap:            4px;
  }

  .evcc-setup-map-list-label {
    font-size:      0.74rem;
    font-weight:    600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color:          var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    margin-bottom:  2px;
  }

  .evcc-setup-map-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         6px 10px;
    border-radius:   6px;
    background:      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 10%, transparent);
    border:          1px solid color-mix(in srgb, var(--evcc-sem-success, #22c55e) 24%, transparent);
  }

  .evcc-setup-map-name {
    font-size:   0.84rem;
    font-weight: 500;
    color:       var(--evcc-text-primary, #f0f2f5);
    overflow:    hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .evcc-setup-map-rooms {
    font-size:   0.78rem;
    color:       var(--evcc-sem-success, #22c55e);
    flex-shrink: 0;
  }

  /* =========================================================
     FOOTER ROW
     ========================================================= */

  .evcc-setup-footer {
    display:     flex;
    align-items: center;
    gap:         10px;
    margin-top:  4px;
  }

  /* =========================================================
     STEP 3 \u2014 MAP CONFIG ROWS
     ========================================================= */

  .evcc-setup-mapconfig-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-mapconfig-row {
    display:        flex;
    flex-direction: column;
    gap:            0;
    border-radius:  8px;
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    overflow:       hidden;
  }

  .evcc-setup-mapconfig-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             10px;
    padding:         10px 12px;
    background:      var(--evcc-surface-input, rgba(255, 255, 255, 0.04));
  }

  .evcc-setup-mapconfig-name {
    font-size:     0.86rem;
    font-weight:   600;
    color:         var(--evcc-text-primary, #f0f2f5);
    overflow:      hidden;
    text-overflow: ellipsis;
    white-space:   nowrap;
  }

  .evcc-setup-mapconfig-actions {
    display:     flex;
    align-items: center;
    gap:         8px;
    flex-shrink: 0;
  }

  .evcc-setup-configured-badge {
    font-size:   0.76rem;
    font-weight: 600;
    color:       var(--evcc-sem-success, #22c55e);
  }

  .evcc-setup-btn.small {
    padding:   5px 12px;
    font-size: 0.80rem;
  }

  /* =========================================================
     ROOM EDITOR \u2014 inline panel below map header
     ========================================================= */

  .evcc-setup-room-editor {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        12px;
    border-top:     1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    background:     var(--evcc-surface-bg, rgba(0, 0, 0, 0.18));
  }

  .evcc-setup-room-editor-hint {
    font-size:   0.80rem;
    color:       var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    line-height: 1.45;
  }

  .evcc-setup-room-list {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }

  /* =========================================================
     INDIVIDUAL ROOM ROW
     ========================================================= */

  .evcc-setup-room-row {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    padding:        8px 10px;
    border-radius:  6px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.07));
    transition:     opacity 150ms ease;
  }

  .evcc-setup-room-row.excluded {
    opacity: 0.45;
  }

  .evcc-setup-room-row-top {
    display:     flex;
    align-items: center;
    gap:         10px;
  }

  .evcc-setup-room-toggle {
    width:           26px;
    height:          26px;
    border-radius:   50%;
    border:          none;
    cursor:          pointer;
    font-size:       0.72rem;
    font-weight:     700;
    display:         flex;
    align-items:     center;
    justify-content: center;
    flex-shrink:     0;
    transition:      background 150ms ease, color 150ms ease;
  }

  .evcc-setup-room-toggle.on {
    background: var(--evcc-sem-success, #22c55e);
    color:      #fff;
  }

  .evcc-setup-room-toggle.off {
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.12));
    color:      var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
  }

  .evcc-setup-room-toggle:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  .evcc-setup-room-name {
    font-size:   0.86rem;
    font-weight: 500;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  /* =========================================================
     FLOOR TYPE CHIPS
     ========================================================= */

  .evcc-setup-floor-chips {
    display:   flex;
    flex-wrap: wrap;
    gap:       5px;
    padding-left: 36px;
  }

  .evcc-setup-floor-chip {
    padding:       4px 10px;
    border-radius: 20px;
    font-size:     0.76rem;
    font-weight:   500;
    cursor:        pointer;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.14));
    background:    var(--evcc-surface-input, rgba(255, 255, 255, 0.07));
    color:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    transition:    background 120ms ease, border-color 120ms ease, color 120ms ease;
    white-space:   nowrap;
  }

  .evcc-setup-floor-chip.active {
    background:   color-mix(in srgb, var(--evcc-accent, #3b82f6) 22%, transparent);
    border-color: var(--evcc-accent, #3b82f6);
    color:        var(--evcc-accent, #3b82f6);
    font-weight:  600;
  }

  .evcc-setup-floor-chip:hover:not(:disabled):not(.active) {
    background: rgba(255, 255, 255, 0.12);
  }

  .evcc-setup-floor-chip:disabled {
    opacity: 0.45;
    cursor:  default;
  }

  /* =========================================================
     DESTRUCTIVE BUTTON VARIANTS
     ========================================================= */

  .evcc-setup-btn.destructive {
    background: var(--evcc-sem-error, #ef4444);
    color:      #fff;
    border:     none;
  }

  .evcc-setup-btn.destructive:hover:not(:disabled) {
    opacity: 0.85;
  }

  .evcc-setup-btn.destructive-ghost {
    background:   transparent;
    color:        var(--evcc-sem-error, #ef4444);
    border:       1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 40%, transparent);
    padding:      5px 12px;
    font-size:    0.80rem;
  }

  .evcc-setup-btn.destructive-ghost:hover:not(:disabled) {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
  }

  /* =========================================================
     DELETE CONFIRMATION PANEL
     ========================================================= */

  .evcc-setup-delete-panel {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        12px;
    border-top:     1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 30%, transparent);
    background:     color-mix(in srgb, var(--evcc-sem-error, #ef4444) 6%, transparent);
  }

  .evcc-setup-delete-badges {
    display:   flex;
    flex-wrap: wrap;
    gap:       5px;
  }

  .evcc-setup-protection-badge {
    padding:       3px 9px;
    border-radius: 20px;
    font-size:     0.74rem;
    font-weight:   600;
    background:    color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 14%, transparent);
    border:        1px solid color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 32%, transparent);
    color:         color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 90%, white 10%);
    white-space:   nowrap;
  }

  .evcc-setup-delete-warning {
    font-size:   0.84rem;
    line-height: 1.5;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-delete-warning strong {
    color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-delete-typed {
    display:        flex;
    flex-direction: column;
    gap:            6px;
  }

  .evcc-setup-delete-typed-hint {
    font-size:   0.80rem;
    color:       var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    line-height: 1.45;
  }

  .evcc-setup-delete-typed-hint strong {
    color:       var(--evcc-text-primary, #f0f2f5);
    font-weight: 700;
  }

  .evcc-setup-delete-input {
    width:         100%;
    box-sizing:    border-box;
    padding:       7px 10px;
    border-radius: 6px;
    border:        1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 40%, transparent);
    background:    var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color:         var(--evcc-text-primary, #f0f2f5);
    font-size:     0.86rem;
    outline:       none;
  }

  .evcc-setup-delete-input:focus {
    border-color: var(--evcc-sem-error, #ef4444);
  }

  .evcc-setup-delete-actions {
    display:     flex;
    align-items: center;
    gap:         8px;
  }
`;var xa=`
  .evcc-mrev-view {
    display: flex;
    flex-direction: column;
    gap: var(--evcc-grid-gap, 12px);
  }

  .evcc-mrev-filter-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .evcc-mrev-grid {
    display: grid;
    gap: var(--evcc-grid-gap, 12px);
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }

  .evcc-mrev-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-panel);
  }

  .evcc-mrev-card-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-mrev-room-name {
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--evcc-text-primary);
  }

  .evcc-mrev-room-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .evcc-mrev-room-id {
    font-size: 0.75rem;
    color: var(--evcc-text-tertiary, var(--evcc-text-secondary));
  }

  .evcc-mrev-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 600;
  }

  .evcc-mrev-badge--ok {
    background: color-mix(in srgb, var(--evcc-success, #4caf50) 15%, transparent);
    color: var(--evcc-success, #4caf50);
  }

  .evcc-mrev-badge--likely {
    background: color-mix(in srgb, var(--evcc-warning, #ff9800) 12%, transparent);
    color: var(--evcc-warning, #ff9800);
    font-style: italic;
  }

  .evcc-mrev-badge--warn {
    background: color-mix(in srgb, var(--evcc-warning, #ff9800) 15%, transparent);
    color: var(--evcc-warning, #ff9800);
  }

  .evcc-mrev-badge--outlier {
    background: color-mix(in srgb, var(--evcc-error, #f44336) 15%, transparent);
    color: var(--evcc-error, #f44336);
  }

  .evcc-mrev-badge--baseline {
    background: color-mix(in srgb, var(--evcc-accent, #6366f1) 15%, transparent);
    color: var(--evcc-accent, #6366f1);
  }

  .evcc-mrev-badge--excluded {
    background: color-mix(in srgb, var(--evcc-text-muted, rgba(240,242,245,0.48)) 18%, transparent);
    color: var(--evcc-text-muted, rgba(240, 242, 245, 0.48));
    font-style: italic;
  }

  .evcc-mrev-no-bounds {
    font-size: 0.82rem;
    color: var(--evcc-text-secondary);
    font-style: italic;
  }

  .evcc-mrev-bounds-block {
    background: color-mix(in srgb, var(--evcc-surface-raised, #fff) 6%, transparent);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 10px 12px;
  }

  .evcc-mrev-bounds-grid {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evcc-mrev-bounds-grid--compact {
    gap: 3px;
  }

  .evcc-mrev-bounds-row {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    align-items: baseline;
    gap: 6px;
    font-size: 0.82rem;
  }

  .evcc-mrev-bounds-row--sub {
    opacity: 0.7;
  }

  .evcc-mrev-bounds-key {
    font-weight: 600;
    color: var(--evcc-text-secondary);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .evcc-mrev-bounds-val {
    color: var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .evcc-mrev-bounds-dim {
    color: var(--evcc-text-secondary);
    font-size: 0.75rem;
    text-align: right;
    white-space: nowrap;
  }

  .evcc-mrev-history {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evcc-mrev-history-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--evcc-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .evcc-mrev-job-entry {
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--evcc-border-default);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-mrev-job-entry--outlier {
    border-color: color-mix(in srgb, var(--evcc-error, #f44336) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-error, #f44336) 5%, transparent);
  }

  .evcc-mrev-job-entry--excluded {
    opacity: 0.55;
    border-color: var(--evcc-border-subtle, rgba(255,255,255,0.06));
  }

  .evcc-mrev-job-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .evcc-mrev-job-id {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .evcc-mrev-job-id--excluded {
    text-decoration: line-through;
    color: var(--evcc-text-muted);
  }

  .evcc-mrev-job-date {
    font-size: 0.75rem;
    color: var(--evcc-text-secondary);
  }

  .evcc-mrev-job-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .evcc-mrev-job-action-btn {
    font-size: 0.70rem;
    padding: 2px 8px;
    height: 20px;
    opacity: 0.85;
  }

  .evcc-mrev-job-action-btn:hover {
    opacity: 1;
  }

  .evcc-mrev-job-pending {
    font-size: 0.75rem;
    color: var(--evcc-text-muted);
    padding: 2px 4px;
  }

  .evcc-mrev-bounds-grid--muted {
    opacity: 0.6;
  }

  .evcc-chip--sm {
    height: 20px;
    padding: 0 8px;
    font-size: 0.70rem;
  }

  .evcc-mrev-card-footer {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    padding-top: 2px;
  }

  .evcc-mrev-clear-btn--disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .evcc-mrev-rebuild-btn {
    background: color-mix(in srgb, var(--evcc-accent, #6366f1) 15%, transparent);
    color: var(--evcc-accent, #6366f1);
    border-color: color-mix(in srgb, var(--evcc-accent, #6366f1) 30%, transparent);
  }

  .evcc-mrev-rebuild-btn:hover {
    background: color-mix(in srgb, var(--evcc-accent, #6366f1) 25%, transparent);
  }

  @media (max-width: 480px) {
    .evcc-mrev-grid {
      grid-template-columns: 1fr;
    }
  }
`;var wa=[aa,ia,na,ca,sa,oa,la,da,Ue,We,ua,ma,va,pa,ha,fa,ga,_a,ba,ya,xa].join(`
`);function Ke(i,e){if(!i||!e)return;let{tokens:t}=e,r=i;re.forEach(a=>{(!Object.prototype.hasOwnProperty.call(t,a.key)||t[a.key]===null||t[a.key]===void 0||t[a.key]==="")&&r.style.removeProperty(a.key)}),Object.entries(t).forEach(([a,n])=>{n!=null&&n!==""&&r.style.setProperty(a,n)})}var Sa=`
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  button {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  .evcc-modal-backdrop {
    position: fixed;
    inset: 0;

    background:
      var(--evcc-modal-backdrop-bg,
      rgba(0, 0, 0, 0.72));

    backdrop-filter:
      blur(var(--evcc-modal-backdrop-blur, 8px));

    display:         flex;
    align-items:     center;
    justify-content: center;
    padding:         16px;
    z-index:         9999;

    font-family: var(--evcc-font-family, var(--paper-font-body1_-_font-family, sans-serif));
    font-size:   14px;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary, #f0f2f5));
  }

  .evcc-modal {
    width:         100%;
    max-width:     480px;
    max-height:    85vh;
    display:       flex;
    flex-direction: column;
    overflow:      hidden;

    background:
      var(--evcc-modal-bg,
      #1c2127);

    border:
      1px solid var(--evcc-modal-border,
      rgba(255, 255, 255, 0.18));

    border-radius:
      var(--evcc-modal-radius, 18px);

    box-shadow:
      var(--evcc-modal-shadow,
      0 20px 60px rgba(0, 0, 0, 0.60));

    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary, #f0f2f5));

    /* =========================================================
       MODAL-LOCAL TOKEN BRIDGE
       =========================================================
       Re-declare canonical tokens as modal-prefixed fallbacks so
       all child components resolve to the modal surface rather
       than the card surface when rendered inside a modal host.
       ========================================================= */

    --evcc-surface-input:
      var(--evcc-modal-input-bg,
      var(--evcc-modal-surface-input,
      rgba(255, 255, 255, 0.06)));

    --evcc-surface-panel:
      var(--evcc-modal-surface-panel,
      #1c2127);

    --evcc-border-default:
      var(--evcc-modal-border-default,
      rgba(255, 255, 255, 0.10));

    --evcc-border-subtle:
      var(--evcc-modal-border-subtle,
      rgba(255, 255, 255, 0.08));

    --evcc-border-strong:
      var(--evcc-modal-border-strong,
      rgba(255, 255, 255, 0.18));

    --evcc-text-primary:
      var(--evcc-modal-text-primary,
      #f0f2f5);

    --evcc-text-secondary:
      var(--evcc-modal-text-secondary,
      rgba(240, 242, 245, 0.72));

    --evcc-text-muted:
      var(--evcc-modal-text-muted,
      rgba(240, 242, 245, 0.48));

    --evcc-accent:
      var(--evcc-modal-accent,
      var(--evcc-accent, #3b82f6));

    --evcc-transition-normal:
      var(--evcc-transition-normal, 150ms ease);

    --evcc-chip-height:
      var(--evcc-chip-height, 24px);

    --evcc-chip-padding:
      var(--evcc-chip-padding, 5px 14px);

    --evcc-chip-radius:
      var(--evcc-chip-radius, 999px);

    --evcc-chip-border:
      var(--evcc-modal-chip-border,
      var(--evcc-border-default));

    --evcc-chip-bg:
      var(--evcc-modal-chip-bg,
      var(--evcc-surface-input));

    --evcc-chip-text:
      var(--evcc-modal-chip-text,
      var(--evcc-text-secondary));

    --evcc-chip-font-size:
      var(--evcc-chip-font-size, 0.82rem);

    --evcc-chip-font-weight:
      var(--evcc-chip-font-weight, 500);

    --evcc-chip-hover-bg:
      var(--evcc-modal-chip-hover-bg,
      var(--evcc-surface-panel));

    --evcc-chip-hover-text:
      var(--evcc-modal-chip-hover-text,
      var(--evcc-text-primary));

    --evcc-chip-hover-border:
      var(--evcc-modal-chip-hover-border,
      var(--evcc-border-strong));

    --evcc-chip-icon-height:
      var(--evcc-chip-icon-height, 24px);

    --evcc-chip-icon-padding:
      var(--evcc-chip-icon-padding, 4px 8px);

    --evcc-chip-icon-size:
      var(--evcc-chip-icon-size, 0.8rem);
  }

  .evcc-modal-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         var(--evcc-modal-padding, 14px 16px 12px);
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
    gap:             12px;
    background:
      var(--evcc-modal-header-bg,
      transparent);
  }

  .evcc-modal-title {
    font-size:      1rem;
    font-weight:    700;
    color:
      var(--evcc-modal-text-primary,
      var(--evcc-text-primary));
    overflow:       hidden;
    text-overflow:  ellipsis;
    white-space:    nowrap;
  }

  .evcc-room-editor-fields,
  .evcc-modal-body {
    flex:           1;
    overflow-y:     auto;
    padding:        var(--evcc-modal-padding, 20px);
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-modal-section-gap, 28px);
  }

  .evcc-editor-field-group {
    display:        flex;
    flex-direction: column;
    gap:            12px;
  }

  .evcc-field-label {
    font-size:      0.72rem;
    font-weight:    600;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding-top:    4px;
  }

  ${Ge}

  .evcc-chip--save {
    background:
      var(--evcc-modal-chip-active-bg,
      var(--evcc-modal-accent-bg,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 22%, transparent)));

    color:
      var(--evcc-modal-chip-active-text,
      var(--evcc-modal-accent-text,
      var(--evcc-modal-accent, var(--evcc-accent))));

    border-color:
      var(--evcc-modal-chip-active-border,
      var(--evcc-modal-accent-border,
      color-mix(in srgb, var(--evcc-modal-accent, var(--evcc-accent)) 45%, transparent)));

    font-weight: 600;
  }

  .evcc-chip--custom {
    background:
      var(--evcc-modal-chip-bg,
      color-mix(in srgb, var(--evcc-modal-text-muted, var(--evcc-text-muted)) 18%, transparent));

    color:
      var(--evcc-modal-chip-text,
      var(--evcc-modal-warning-text,
      var(--evcc-text-secondary)));

    border-color:
      var(--evcc-modal-chip-border,
      var(--evcc-modal-warning-border,
      var(--evcc-border-strong)));

    font-style: italic;
    cursor:     default;
  }

  ${Je}
  ${Ue}
  ${We}

  .evcc-modal-footer {
    display:         flex;
    align-items:     center;
    justify-content: flex-end;
    gap:             8px;
    padding:         var(--evcc-modal-padding, 12px 16px 14px);
    border-top:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
    background:
      var(--evcc-modal-footer-bg,
      transparent);
  }

  .evcc-room-editor-include-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         12px 20px;
    border-bottom:
      1px solid var(--evcc-modal-border-subtle,
      var(--evcc-border-subtle));
    flex-shrink:     0;
  }

  .evcc-room-editor-include-label {
    font-size: 0.88rem;
    color:
      var(--evcc-modal-text-secondary,
      var(--evcc-text-secondary));
  }

  .evcc-room-profile-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .evcc-room-profile-meta {
    font-size: 0.80rem;
    color:
      var(--evcc-modal-text-muted,
      var(--evcc-text-muted));
    line-height: 1.45;
  }

  .evcc-chip--toggle-include {
    flex-shrink: 0;
  }

  .evcc-chip--toggle-include.active {
    background:
      var(--evcc-chip-included-bg,
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 18%, transparent));

    color:
      var(--evcc-chip-included-text,
      var(--evcc-sem-success, #22c55e));

    border-color:
      var(--evcc-chip-included-border,
      color-mix(in srgb, var(--evcc-sem-success, #22c55e) 40%, transparent));
  }

  .evcc-room-editor-carpet-notice {
    margin:        0 16px;
    padding:       8px 12px;
    border-radius: 6px;
    background:
      var(--evcc-modal-warning-bg,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b)) 12%, transparent));

    border:
      1px solid var(--evcc-modal-warning-border,
      color-mix(in srgb, var(--evcc-modal-warning-text, var(--evcc-sem-warning, #f59e0b)) 30%, transparent));

    color:
      var(--evcc-modal-warning-text,
      var(--evcc-sem-warning, #f59e0b));

    font-size:   0.82rem;
    font-weight: 500;
    flex-shrink: 0;
  }

  @media (prefers-color-scheme: light) {
    .evcc-modal {
      background:
        var(--evcc-modal-bg,
        #ffffff);

      border:
        1px solid var(--evcc-modal-border,
        rgba(15, 23, 42, 0.12));

      box-shadow:
        var(--evcc-modal-shadow,
        0 20px 60px rgba(0, 0, 0, 0.22));

      color:
        var(--evcc-modal-text-primary,
        #0f172a);

      --evcc-surface-panel:
        var(--evcc-modal-surface-panel,
        #ffffff);

      --evcc-surface-input:
        var(--evcc-modal-input-bg,
        var(--evcc-modal-surface-input,
        rgba(15, 23, 42, 0.05)));

      --evcc-border-default:
        var(--evcc-modal-border-default,
        rgba(15, 23, 42, 0.10));

      --evcc-border-subtle:
        var(--evcc-modal-border-subtle,
        rgba(15, 23, 42, 0.06));

      --evcc-border-strong:
        var(--evcc-modal-border-strong,
        rgba(15, 23, 42, 0.16));

      --evcc-text-primary:
        var(--evcc-modal-text-primary,
        #0f172a);

      --evcc-text-secondary:
        var(--evcc-modal-text-secondary,
        rgba(15, 23, 42, 0.74));

      --evcc-text-muted:
        var(--evcc-modal-text-muted,
        rgba(15, 23, 42, 0.50));
    }

    .evcc-modal-backdrop {
      background:
        var(--evcc-modal-backdrop-bg,
        rgba(15, 23, 42, 0.28));
    }
  }
`;function te(i){let e=i._state;if(!e||typeof e.resolvedTheme!="function")return;let t=e.resolvedTheme();Ke(i,t),i._modalHost&&document.body.contains(i._modalHost)&&Ke(i._modalHost,t)}function $i(i){if(!i)return null;let e=i.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);if(!e)return null;let[,t,r,a]=e;return"#"+[t,r,a].map(n=>parseInt(n,10).toString(16).padStart(2,"0")).join("")}var Ra=new Set(["--evcc-accent","--evcc-surface-base","--evcc-text-primary","--evcc-radius-card"]),Mi=300,Ea=6;function ka(i){i._bindThemeEditor=function(){this._bindThemeTabs(),this._bindThemePresets(),this._bindThemeGroupFilters(),this._bindThemeGroupToggles(),this._bindThemeGlobalSearch(),this._bindThemeGroupSearch(),this._bindThemeTokenEdits(),this._bindThemeAlphaEdits(),this._bindThemeColorMixEdits(),this._bindThemeTokenResets(),this._bindThemeGroupResets(),this._bindThemeColorPickerFromAlphaInput(),this._bindThemeActions()},i._bindThemeTabs=function(){this.card._onAll("[data-theme-tab]","click",e=>{let t=e.currentTarget.dataset.themeTab;this.card._state.setThemeSubTab(t),this.card._scheduleRender()})},i._bindThemePresets=function(){this.card._onAll("[data-theme-preset]","click",async e=>{let t=e.currentTarget.dataset.themePreset;if(!t)return;let r=await this.card._actions.setActiveTheme(this.card._config.vacuum_entity_id,t);if(r?.ok===!1){alert(r.reason||"Unable to select theme.");return}let a=r?.active_theme_id??r?.theme_id??t;this.card._state.applyThemeActivation(a,{clearDraft:r?.draft_dirty===!1}),te(this.card),this.card._scheduleRender(),await this._refreshThemeFromBackend({fallbackActiveThemeId:a,fallbackDraftDirty:!1})})},i._bindThemeGroupFilters=function(){this.card._onAll("[data-theme-group-filter]","click",e=>{let t=e.currentTarget.dataset.themeGroupFilter||"all";this.card._state.setThemeGroupFilter(t),K.includes(t)&&this.card._state.setThemeFocusedGroup(t),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()})},i._bindThemeGroupToggles=function(){this.card._onAll("[data-theme-group-toggle]","click",e=>{let t=e.currentTarget.dataset.themeGroupToggle;t&&(this.card._state.setThemeFocusedGroup(t),this.card._state.toggleThemeGroup(t),this.card._scheduleRender())})},i._bindThemeGlobalSearch=function(){this.card._on(this.card.$("[data-theme-search]"),"input",e=>{this.card._state.setThemeSearchQuery(e.target.value),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-theme-modified-only]"),"change",e=>{this.card._state.setThemeModifiedOnly(e.target.checked),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()})},i._bindThemeGroupSearch=function(){this.card._onAll("[data-theme-group-search]","input",e=>{let t=e.currentTarget.dataset.themeGroupSearch;t&&(this.card._state.setThemeFocusedGroup(t),this.card._state.setThemeGroupSearchQuery(t,e.target.value),this.card._scheduleRender())})},i._bindThemeTokenEdits=function(){this.card._onAll("[data-theme-token]","input",async e=>{let t=e.currentTarget.dataset.themeToken,r=ge[t];if(!r)return;let a=e.currentTarget.type==="range",n=e.currentTarget.value;this.card._state.setThemeFocusedGroup(r.group),this._syncThemeRowInputs(e.currentTarget,t),this._isScalarThemeType(r.type)&&(n=this._formatScalarThemeValue(n,r,e.currentTarget));let c=this._buildDraftPayload(t,n,r);if(!Object.keys(c).length)return;!a&&this._isSettledThemeValue(n,r)&&await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,c),this.card._state.applyThemeDraftPatch(c),te(this.card)}),this.card._onAll("[data-theme-color-input]","change",async e=>{let t=e.currentTarget.dataset.themeColorInput,r=ge[t];if(!r)return;let a=e.currentTarget.value||"";this.card._state.setThemeFocusedGroup(r.group),this._syncThemeRowInputs(e.currentTarget,t,a);let n=this._buildDraftPayload(t,a,r);Object.keys(n).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,n),this.card._state.applyThemeDraftPatch(n),te(this.card),this.card._scheduleDeferredRender?.())}),this.card._onAll("[data-theme-token]","change",async e=>{if(e.currentTarget.type==="range"){let r=e.currentTarget.dataset.themeToken,a=ge[r];if(a){let n=e.currentTarget.value;this._isScalarThemeType(a.type)&&(n=this._formatScalarThemeValue(n,a,e.currentTarget));let c=this._buildDraftPayload(r,n,a);Object.keys(c).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,c),this.card._state.applyThemeDraftPatch(c),te(this.card))}}this.card._scheduleDeferredRender?.()})},i._bindThemeAlphaEdits=function(){this.card._onAll("[data-theme-alpha]","input",e=>{let t=e.currentTarget.dataset.themeAlpha;if(!t)return;let r=ge[t];r?.group&&this.card._state.setThemeFocusedGroup(r.group);let a=this._clampThemeAlphaPercent(e.currentTarget.value);this._syncThemeAlphaControls(t,a,e.currentTarget),this.card._state.applyThemeDraftPatch({alpha:{[t]:a/100}}),te(this.card)}),this.card._onAll("[data-theme-alpha]","change",async e=>{let t=e.currentTarget.dataset.themeAlpha;if(!t)return;let r=this._clampThemeAlphaPercent(e.currentTarget.value);await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,{alpha:{[t]:r/100}}),te(this.card),this.card._scheduleDeferredRender?.()})},i._clampThemeAlphaPercent=function(e){let t=Number(e);return Number.isNaN(t)?100:Math.max(0,Math.min(100,Math.round(t)))},i._syncThemeAlphaControls=function(e,t,r=null){let a=r?r.closest(".evcc-token-row"):this.card.shadowRoot?.querySelector(`[data-theme-alpha="${e}"]`)?.closest(".evcc-token-row");if(!a)return;let n=a.querySelector(`[data-theme-alpha="${e}"]`),c=a.querySelector(`[data-theme-alpha-bubble="${e}"]`),s=a.querySelector(`[data-theme-alpha-indicator="${e}"]`),o=a.querySelector(".token-alpha-shell"),l=a.querySelector(".token-alpha-rail");if(n&&(n.value=String(t)),!n)return;let d=Number(n.min)||0,u=Number(n.max)||100,v=Number(n.value)||0,m=u===d?0:(v-d)/(u-d);if(s&&l){let p=l.clientWidth,f=m*p;s.style.left=`${f}px`}if(c&&o){let p=o.clientWidth,f=m*p;c.style.left=`${f}px`,c.textContent=`${v}%`}},i._syncThemeRowInputs=function(e,t,r=null){let a=e.closest(".evcc-token-row");if(!a)return;let n=r??e.value;a.querySelectorAll(`[data-theme-token="${t}"], [data-theme-color-input="${t}"]`).forEach(c=>{c!==e&&(c.value=n)}),this._syncThemeScalarControls(a,t,n)},i._syncThemeScalarControls=function(e,t,r){if(!e)return;let a=e.querySelector(`[data-theme-slider-bubble="${t}"]`);if(!a)return;let n=e.dataset.themeTokenUnit||"",c=e.querySelector(`input[type="range"][data-theme-token="${t}"]`);c&&(c.value=r),a.textContent=`${r}${n}`},i._isSettledThemeValue=function(e,t){if(!t||t.type!=="color")return!0;let r=String(e||"").trim();return!!(!r||/^#[0-9a-fA-F]{6}$/.test(r)||/^#[0-9a-fA-F]{8}$/.test(r)||/^color-mix\(.*%.*\)$/is.test(r)||/^var\(--[\w-]+\)$/.test(r))},i._isScalarThemeType=function(e){return e==="size"||e==="number"||e==="duration"},i._extractThemeScalarUnit=function(e,t=""){let r=String(t||"").trim();if(e?.type==="duration"){let a=r.match(/^-?\d*\.?\d+\s*(ms|s)$/i);return a?a[1].toLowerCase():"ms"}if(e?.type==="size"){let a=r.match(/^-?\d*\.?\d+\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);return a?a[1].toLowerCase():"px"}return""},i._formatScalarThemeValue=function(e,t,r=null){let a=parseFloat(String(e||"").trim());if(Number.isNaN(a))return"";if(t?.type==="number")return`${a}`;let n=r?.closest(".evcc-token-row")||null,c=n?.dataset.themeTokenUnit?`${a}${n.dataset.themeTokenUnit}`:e,s=this._extractThemeScalarUnit(t,c);return`${a}${s}`},i._buildDraftPayload=function(e,t,r=null){let a=r||ge[e];return a?a.type==="color"?{tokens:{[e]:t},colors:{[e]:t}}:a.type==="alpha"?{alpha:{[e]:t}}:{tokens:{[e]:t}}:{}},i._bindThemeColorMixEdits=function(){this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']","input",e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row");if(!r)return;let a=Math.max(0,Math.min(100,Math.round(Number(e.currentTarget.value)))),n=r.querySelector(`[data-colormix-ratio-label="${t}"]`);n&&(n.textContent=`${a}%`);let c=this._readColorMixExpr(r,t,{ratio:a});c&&(this.card._state.applyThemeDraftPatch({tokens:{[t]:c},colors:{[t]:c}}),te(this.card),this._syncColorMixPreview(r,c))}),this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']","change",async e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=Math.max(0,Math.min(100,Math.round(Number(e.currentTarget.value)))),n=this._readColorMixExpr(r,t,{ratio:a});if(!n)return;let c={tokens:{[t]:n},colors:{[t]:n}};await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,c),this.card._state.applyThemeDraftPatch(c),te(this.card),this.card._scheduleDeferredRender?.()}),this.card._onAll("[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']","change",async e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=this._readColorMixExpr(r,t);if(!a)return;let n={tokens:{[t]:a},colors:{[t]:a}};await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,n),this.card._state.applyThemeDraftPatch(n),te(this.card),this._syncColorMixPreview(r,a),this.card._scheduleDeferredRender?.()}),this.card._onAll("[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']","input",e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=this._readColorMixExpr(r,t);a&&this._syncColorMixPreview(r,a)})},i._readColorMixExpr=function(e,t,r={}){if(!e)return null;let a=e.querySelector('[data-colormix-part="color1"]'),n=e.querySelector('[data-colormix-part="color2"]'),c=e.querySelector('[data-colormix-part="ratio"]');if(!a||!n||!c)return null;let s=(a.value||"").trim(),o=(n.value||"").trim(),l="ratio"in r?r.ratio:Math.max(0,Math.min(100,Math.round(Number(c.value))));return!s||!o?null:`color-mix(in srgb, ${s} ${l}%, ${o} ${100-l}%)`},i._syncColorMixPreview=function(e,t){if(!e||!t)return;let r=e.querySelector(".token-colormix-preview");r&&(r.style.background=t)},i._bindThemeTokenResets=function(){this.card._onAll("[data-theme-reset]","click",async e=>{let t=e.currentTarget.dataset.themeReset,r=ge[t];if(!r)return;this.card._state.setThemeFocusedGroup(r.group);let a=this._buildDraftResetPayload(t,r);Object.keys(a).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,a),this.card._state.applyThemeDraftPatch(a),await this._refreshThemeFromBackend())})},i._buildDraftResetPayload=function(e,t){return t.type==="color"?{tokens:{[e]:null},colors:{[e]:null},alpha:{[e]:null}}:t.type==="alpha"?{alpha:{[e]:null}}:{tokens:{[e]:null}}},i._bindThemeGroupResets=function(){this.card._onAll("[data-theme-group-reset]","click",async e=>{e.stopPropagation();let t=e.currentTarget.dataset.themeGroupReset;if(!t)return;this.card._state.setThemeFocusedGroup(t);let r=this._buildThemeGroupResetPayload(t);r&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,r),await this._refreshThemeFromBackend())})},i._buildThemeGroupResetPayload=function(e){let t=this.card._state.filteredThemeTokensForGroup(e,re,{excludeKeys:Ra}),{sources:r}=this.card._state.resolvedTheme(),a={},n={},c={},s=!1;if(t.forEach(l=>{(r[l.key]||"ha")==="draft"&&(l.type==="color"?(a[l.key]=null,n[l.key]=null,c[l.key]=null,s=!0):l.type==="alpha"?(c[l.key]=null,s=!0):(a[l.key]=null,s=!0))}),!s)return null;let o={};return Object.keys(a).length&&(o.tokens=a),Object.keys(n).length&&(o.colors=n),Object.keys(c).length&&(o.alpha=c),o},i._bindThemeColorPickerFromAlphaInput=function(){this._alphaTapMap||(this._alphaTapMap=new Map);let e=this._alphaTapMap;this.card._onAll("[data-color-swatch]","pointerdown",t=>{let a=t.currentTarget.dataset.colorSwatch;if(!a)return;let n=t.clientX,c=t.clientY,s=!1,o=v=>{let m=Math.abs(v.clientX-n),p=Math.abs(v.clientY-c);(m>Ea||p>Ea)&&(s=!0)},l=()=>{window.removeEventListener("pointermove",o),window.removeEventListener("pointerup",d),window.removeEventListener("pointercancel",u)},d=()=>{let v=Date.now(),m=e.get(a)||0,p=!s&&v-m<Mi;if(e.set(a,v),p){let h=this.card.shadowRoot?.querySelector(`[data-theme-alpha="${a}"]`)?.closest(".evcc-token-row")?.querySelector(`[data-theme-color-input="${a}"]`);if(h){let y=this._resolveTokenColorHex(a);y&&(h.value=y),h.click()}}l()},u=()=>{l()};window.addEventListener("pointermove",o),window.addEventListener("pointerup",d),window.addEventListener("pointercancel",u)})},i._resolveTokenColorHex=function(e){let t=this.card.shadowRoot;if(!t)return null;try{let r=document.createElement("div");r.style.cssText=`
        position: absolute;
        left: -9999px;
        width: 1px;
        height: 1px;
        background-color: var(${e});
        pointer-events: none;
      `,t.appendChild(r);let a=getComputedStyle(r).backgroundColor;return t.removeChild(r),$i(a)}catch{return null}},i._bindThemeActions=function(){this.card._on(this.card.$("[data-action='save-theme']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t;if(e.activeThemeId)t=await this.card._actions.overwriteTheme(this.card._config.vacuum_entity_id,e.activeThemeId);else{let r=prompt("Enter a name for your new theme:");if(!r)return;t=await this.card._actions.saveThemeAsNew(this.card._config.vacuum_entity_id,r,!1)}if(t?.ok!==!1){let r=t?.active_theme_id??t?.theme_id??e.activeThemeId;this.card._state.applyThemeActivation(r,{clearDraft:!0})}await this._refreshThemeFromBackend()}),this.card._on(this.card.$("[data-action='reset-draft']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t=await this.card._actions.revertDraft(this.card._config.vacuum_entity_id);if(t?.ok!==!1){let r=t?.active_theme_id??e.activeThemeId;this.card._state.applyThemeActivation(r,{clearDraft:!0})}await this._refreshThemeFromBackend()}),this.card._onAll("[data-action='delete-preset']","click",async e=>{e.stopPropagation();let t=e.currentTarget.dataset.presetId;t&&confirm(`Delete theme "${t}"?`)&&(await this.card._actions.deleteTheme(t),await this._refreshThemeFromBackend())}),this.card._on(this.card.$("[data-action='export-theme']"),"click",async()=>{let t=this.card._state._ensureThemeState().activeThemeId;if(!t){alert("No active theme to export.");return}let r=await this.card._actions.exportTheme(t),a=JSON.stringify(r,null,2);try{await navigator.clipboard.writeText(a),alert("Theme copied to clipboard!")}catch{console.log(a),alert("Copied to console instead.")}}),this.card._on(this.card.$("[data-action='import-theme']"),"click",async()=>{let e=prompt("Paste theme JSON here:");if(e)try{let t=JSON.parse(e);await this.card._actions.importTheme(t),await this._refreshThemeFromBackend(),alert("Theme imported successfully.")}catch{alert("Invalid theme JSON.")}})},i._refreshThemeFromBackend=async function(e={}){let t=e?.fallbackActiveThemeId??null,r=e?.fallbackDraftDirty,a=await this.card._actions.getThemeLibrary();a&&this.card._state.setThemeLibrary(a),t&&this.card._state.getActiveTheme()?.id!==t&&this.card._state._ensureThemeState().activeThemeId!==t&&this.card._state.applyThemeActivation(t,{clearDraft:r===!1}),this._autoOpenMatchingThemeGroups(),te(this.card),this.card._scheduleRender()},i._autoOpenMatchingThemeGroups=function(){let e=this.card._state._ensureThemeState();K.forEach(t=>{this.card._state.shouldForceThemeGroupOpenForSearch(t,re,{excludeKeys:Ra})&&(e.groupOpen[t]=!0)})}}var b={ROOMS:"rooms",MAINTENANCE:"maintenance",BASE_STATION:"base_station",METRICS:"metrics",LEARNING_REVIEW:"learning_review",ROOM_RULES:"room_rules",THEME:"theme",MAPPING_ARCHIVE:"mapping",MAP_CONFIG:"map_config",MAPPING_REVIEW:"mapping_review",SETUP:"setup"},Oe=[b.ROOMS,b.MAINTENANCE,b.BASE_STATION,b.METRICS,b.LEARNING_REVIEW,b.ROOM_RULES,b.THEME,b.MAP_CONFIG,b.MAPPING_REVIEW,b.SETUP];function Ta(i){let e=i._state,t=i._renderers;return{card:i,state:e,renderers:t,vacuumName:e.vacuumDisplayName(),vacuumStatus:e.vacuumState()??"unknown",battery:e.batteryLevel(),view:i._view??b.ROOMS}}function Ii(i){return{cleaning:"cleaning",docked:"docked",returning:"returning",error:"error",paused:"paused"}[i]||""}function $a(i){let{renderers:e,vacuumName:t,vacuumStatus:r,battery:a,view:n}=i,c=a!=null?`${a}%`:"";return`
    <div class="evcc-header">

      <div class="evcc-header-left">
        <div class="evcc-vacuum-name">
          ${e.escapeHtml(t)}
        </div>

        <div class="evcc-vacuum-status">
          <span class="evcc-status-dot ${Ii(r)}"></span>
          <span>${e.escapeHtml(r)}</span>
          ${c?`<span class="evcc-battery">${e.escapeHtml(c)}</span>`:""}
        </div>
      </div>

    </div>

    <div class="evcc-nav">

      <button class="evcc-nav-tab ${n===b.ROOMS?"active":""}"
              data-view="${b.ROOMS}">
        Rooms
      </button>

      <button class="evcc-nav-tab ${n===b.MAINTENANCE?"active":""}"
              data-view="${b.MAINTENANCE}">
        Maintenance
      </button>

      <button class="evcc-nav-tab ${n===b.BASE_STATION?"active":""}"
              data-view="${b.BASE_STATION}">
        Base Station
      </button>

      <button class="evcc-nav-tab ${n===b.METRICS?"active":""}"
              data-view="${b.METRICS}">
        Metrics
      </button>

      <button class="evcc-nav-tab ${n===b.LEARNING_REVIEW?"active":""}"
              data-view="${b.LEARNING_REVIEW}">
        Learning Review
      </button>

      <button class="evcc-nav-tab ${n===b.ROOM_RULES?"active":""}"
              data-view="${b.ROOM_RULES}">
        Room Rules
      </button>

      <button class="evcc-nav-tab ${n===b.THEME?"active":""}"
              data-view="${b.THEME}">
        Theme
      </button>

      <button class="evcc-nav-tab ${n===b.MAPPING_REVIEW?"active":""}"
              data-view="${b.MAPPING_REVIEW}">
        Map Bounds
      </button>

      <button class="evcc-nav-tab ${n===b.SETUP?"active":""}"
              data-view="${b.SETUP}">
        Setup
      </button>

    </div>
  `}function Ma(i){let{view:e,renderers:t}=i;switch(e){case b.ROOMS:return t.renderRoomsView?.(i)??'<div class="evcc-empty">Rooms view unavailable</div>';case b.MAINTENANCE:return t.renderMaintenanceView?.(i)??'<div class="evcc-empty">Maintenance view unavailable</div>';case b.BASE_STATION:return t.renderBaseStationView?.(i)??'<div class="evcc-empty">Base station view unavailable</div>';case b.METRICS:return t.renderMetricsView?.(i)??'<div class="evcc-empty">Metrics view unavailable</div>';case b.LEARNING_REVIEW:return t.renderLearningReviewView?.(i)??'<div class="evcc-empty">Learning review view unavailable</div>';case b.ROOM_RULES:return t.renderRoomRulesView?.(i)??'<div class="evcc-empty">Room rules view unavailable</div>';case b.THEME:return t.renderThemeView?.(i)??'<div class="evcc-empty">Theme view unavailable</div>';case b.MAP_CONFIG:return t.renderMapConfigView?.(i)??'<div class="evcc-empty">Map config unavailable</div>';case b.MAPPING_REVIEW:return t.renderMappingReviewView?.(i)??'<div class="evcc-empty">Mapping bounds review unavailable</div>';case b.SETUP:return t.renderSetupView?.(i)??'<div class="evcc-empty">Setup unavailable</div>';default:return'<div class="evcc-empty">Unknown view</div>'}}function Aa(i){i._bindMap=function(){let e=this.card.shadowRoot;if(!e)return;this._bindMapViewToggle(e),this._bindMapPolygons(e),this._bindMapTooltip(e),this._bindMapChips(e),this._bindMapConfigEntry(e),this._bindMapConfig(e),this._bindMapZoomPan(e),this._bindMapAnimal(e),this._bindMapAnimalSelect(e),(this.card._view===b.MAP_CONFIG||this.card._state.isMapViewActive?.())&&this._ensureMapSegments()},i._bindMapViewToggle=function(e){e.querySelectorAll("[data-action='set-map-view']").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.mapView==="true";this.card._state.setMapViewActive(r),r&&(this._syncSegmentsFromRooms(),this._ensureMapSegments()),this.card._scheduleRender()})})},i._syncSegmentsFromRooms=function(){if(!this.card._state.mapSegments().length)return;let e=this.card._state.getRoomsForActiveMap?.()??[];this.card._state.clearSegmentSelection(),[...e].filter(t=>t.enabled).sort((t,r)=>(t.order??0)-(r.order??0)).forEach(t=>this.card._state.enableSegmentForRoom(t.id))},i._bindMapPolygons=function(e){e.querySelectorAll("[data-action='toggle-segment']").forEach(t=>{let r=null;t.addEventListener("click",a=>{if(a.stopPropagation(),this.card._mapDragOccurred){this.card._mapDragOccurred=!1;return}let n=t.dataset.segmentId;if(!n)return;if(r){clearTimeout(r),r=null;let s=this.card._state.getRoomsForActiveMap?.()??[],o=this.card._state.roomIdForSegment(n),l=o!=null?s.find(d=>String(d.id)===String(o)):null;l&&(this.card._state.openRoomEditor(l.mapId,l.id),this.card._scheduleRender());return}let c=this.card._state.isSegmentSelected(n);r=setTimeout(()=>{r=null,this.card._state.toggleSegmentSelected(n);let s=this.card._state.getRoomsForActiveMap?.()??[],o=this.card._state.roomIdForSegment(n),l=o!=null?s.find(d=>String(d.id)===String(o)):null;l&&this.card._actions.toggleRoomEnabled(l.mapId,l.id,c).then(()=>this.card._scheduleRender()).catch(d=>console.error("[eufy-vacuum-command-center] Room sync failed:",d)),this.card._scheduleRender()},220)})})},i._bindMapTooltip=function(e){let t=e.querySelector(".evcc-map-tooltip"),r=e.querySelector(".evcc-map-container");if(!t||!r)return;let a=(s,o)=>{let l=s.dataset.label??"",d=s.dataset.hint??"";t.innerHTML=`<span class="evcc-map-tooltip-label">${l}</span>`+(d?`<span class="evcc-map-tooltip-hint">${d}</span>`:""),t.classList.add("evcc-map-tooltip--visible"),n(o)},n=s=>{let o=r.getBoundingClientRect(),l=s.clientX-o.left+14,d=s.clientY-o.top-t.offsetHeight-8;t.style.left=`${Math.min(l,o.width-t.offsetWidth-8)}px`,t.style.top=`${Math.max(8,d)}px`},c=()=>t.classList.remove("evcc-map-tooltip--visible");e.querySelectorAll("[data-action='toggle-segment']").forEach(s=>{s.addEventListener("pointerenter",o=>a(s,o)),s.addEventListener("pointermove",o=>n(o)),s.addEventListener("pointerleave",c),s.addEventListener("click",c)})},i._bindMapChips=function(e){e.querySelectorAll("[data-action='map-chip-activate']").forEach(t=>{let r=null;t.addEventListener("click",a=>{a.stopPropagation();let n=t.dataset.roomId;if(n){if(r){clearTimeout(r),r=null;let s=(this.card._state.getRoomsForActiveMap?.()??[]).find(o=>String(o.id)===String(n));s&&(this.card._state.openRoomEditor(s.mapId,s.id),this.card._scheduleRender());return}r=setTimeout(()=>{r=null},220)}})})},i._bindMapConfigEntry=function(e){e.querySelectorAll("[data-action='open-map-config']").forEach(t=>{t.addEventListener("click",()=>{this._ensureMapSegments(),this.card.setView(b.MAP_CONFIG)})})},i._bindMapConfig=function(e){e.querySelectorAll("[data-action='map-config-back']").forEach(t=>{t.addEventListener("click",()=>{this.card.setView(b.ROOMS)})}),e.querySelectorAll("[data-action='config-select-segment']").forEach(t=>{t.addEventListener("click",r=>{r.stopPropagation();let a=t.dataset.segmentId;if(!a)return;let n=this.card._state.configSelectedSegmentId();this.card._state.setConfigSelectedSegmentId(n===a?null:a),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='upload-map-variant']").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.variant,a=e.querySelector(`[data-variant-input="${r}"]`);if(!a)return;let n=async()=>{a.removeEventListener("change",n);let c=a.files?.[0];if(!c)return;a.value="";let o=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??null;if(!o){this.card._state.setMapActionStatus({type:"upload",variant:r,status:"error",message:"No active map found"}),this.card._scheduleRender();return}this.card._state.setMapActionStatus({type:"upload",variant:r,status:"busy"}),this.card._scheduleRender();try{let l=await Ai(c);await this.card._actions.uploadMapImage(o,l,{variant:r}),this.card._state.setMapActionStatus({type:"analyze",status:"busy"}),this.card._scheduleRender(),await this.card._actions.analyzeMapImage(o,{force_reanalyze:!0}),await this.card._actions.getMapSegments(o),this.card._state.clearMapActionStatus(),this.card._scheduleRender()}catch(l){console.error("[eufy-vacuum-command-center] Map upload failed:",l),this.card._state.setMapActionStatus({type:"upload",variant:r,status:"error",message:l?.message??"Upload failed"}),this.card._scheduleRender()}};a.addEventListener("change",n),a.click()})}),e.querySelectorAll("[data-action='analyze-map']").forEach(t=>{t.addEventListener("click",async()=>{let a=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??null;if(a){this.card._state.setMapActionStatus({type:"analyze",status:"busy"}),this.card._scheduleRender();try{await this.card._actions.analyzeMapImage(a,{force_reanalyze:!0}),await this.card._actions.getMapSegments(a),this.card._state.clearMapActionStatus(),this.card._scheduleRender()}catch(n){console.error("[eufy-vacuum-command-center] Map analysis failed:",n),this.card._state.setMapActionStatus({type:"analyze",status:"error",message:n?.message??"Analysis failed"}),this.card._scheduleRender()}}})}),e.querySelectorAll("[data-action='nudge-segment']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.segmentId,a=Number(t.dataset.dx??0),n=Number(t.dataset.dy??0),s=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!(!r||!s))try{await this.card._actions.adjustMapSegment(s,r,{delta_x:a,delta_y:n}),await this.card._actions.getMapSegments(s),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(o){console.error("[eufy-vacuum-command-center] Nudge failed:",o)}})}),e.querySelectorAll("[data-action='reset-segment-adjustment']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.segmentId,n=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!r||!n)return;let c=this.card._state.mapSegments().find(d=>String(d.segment_id)===String(r));if(!c)return;let s=c.translation_offset,o=Array.isArray(s)?s[0]??0:s?.x??0,l=Array.isArray(s)?s[1]??0:s?.y??0;if(!(o===0&&l===0))try{await this.card._actions.adjustMapSegment(n,r,{delta_x:-o,delta_y:-l}),await this.card._actions.getMapSegments(n),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(d){console.error("[eufy-vacuum-command-center] Reset failed:",d)}})}),e.querySelectorAll("[data-action='adjust-edge']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.segmentId,a=t.dataset.edge,n=Number(t.dataset.delta??0),s=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!r||!s||!a)return;let o={[`edge_${a}`]:n};try{await this.card._actions.adjustMapSegment(s,r,o),await this.card._actions.getMapSegments(s),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(l){console.error("[eufy-vacuum-command-center] Edge adjust failed:",l)}})}),e.querySelectorAll("[data-action='select-vertex']").forEach(t=>{t.addEventListener("click",r=>{r.stopPropagation();let a=Number(t.dataset.vertexIndex),n=this.card._state.configSelectedVertexIndex?.();this.card._state.setConfigSelectedVertexIndex(n===a?null:a),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='nudge-vertex']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.segmentId,a=Number(t.dataset.vertexIndex),n=Number(t.dataset.dx??0),c=Number(t.dataset.dy??0),o=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!(!r||!o))try{await this.card._actions.adjustMapSegment(o,r,{vertex_moves:[{index:a,delta_x:n,delta_y:c}]}),await this.card._actions.getMapSegments(o),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(l){console.error("[eufy-vacuum-command-center] Vertex nudge failed:",l)}})}),e.querySelectorAll("[data-action='reset-vertex']").forEach(t=>{t.addEventListener("click",async()=>{let r=t.dataset.segmentId,a=Number(t.dataset.vertexIndex),c=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!r||!c)return;let o=(this.card._state.mapSegments().find(l=>String(l.segment_id)===String(r))?.vertex_adjustment??[]).find(l=>l.index===a);if(!(!o||!o.delta_x&&!o.delta_y))try{await this.card._actions.adjustMapSegment(c,r,{vertex_moves:[{index:a,delta_x:-(o.delta_x??0),delta_y:-(o.delta_y??0)}]}),await this.card._actions.getMapSegments(c),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(l){console.error("[eufy-vacuum-command-center] Vertex reset failed:",l)}})}),e.querySelectorAll("[data-action='assign-segment-room']").forEach(t=>{t.addEventListener("click",()=>{let r=t.dataset.segmentId,a=t.dataset.roomId;if(!r||!a)return;let n=this.card._state.roomIdForSegment(r);n!=null&&String(n)===String(a)?this.card._state.unassignSegmentRoom(r):this.card._state.assignSegmentRoom(r,a),this.card._scheduleRender()})})},i._ensureMapSegments=async function(){if(this.card._state.mapSegmentsData()||this._mapSegmentsFetching)return;let t=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(t){this._mapSegmentsFetching=!0;try{await this.card._actions.getMapSegments(t),this.card._state.mapSegmentsData()&&(this._syncSegmentsFromRooms(),this.card._scheduleRender())}catch(r){console.error("[eufy-vacuum-command-center] Failed to load map segments:",r)}finally{this._mapSegmentsFetching=!1}}},i._bindMapAnimalSelect=function(e){e.querySelectorAll("[data-action='map-animal-select']").forEach(t=>{t.addEventListener("change",()=>{this.card._state.setMapAnimalSelection?.(t.value),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='map-animal-scale']").forEach(t=>{t.addEventListener("input",()=>{this.card._state.setMapAnimalScale?.(t.value);let r=e.querySelector(".evcc-map-animal"),a=r?.querySelector("animal-svg");if(r&&a){let n=parseFloat(t.value)||1,c=Math.round(64*n)+"px",s=Math.round(44*n)+"px";r.style.width=c,r.style.height=s,a.setAttribute("width",c),a.setAttribute("height",s)}}),t.addEventListener("change",()=>{this.card._scheduleRender()})})},i._bindMapAnimal=function(e){e.querySelectorAll("[data-action='map-dot-click']").forEach(t=>{let r=e.querySelector(".evcc-map-layers");r&&t.addEventListener("pointerdown",a=>{if(a.button!==0)return;a.stopPropagation(),a.preventDefault();let n=t.dataset.anchorKey;if(!n)return;t.setPointerCapture(a.pointerId),t.classList.add("evcc-map-animal--dragging");let c=r.getBoundingClientRect(),s=parseFloat(t.style.left)||0,o=parseFloat(t.style.top)||0,l=a.clientX-c.left-s/100*c.width,d=a.clientY-c.top-o/100*c.height,u=s,v=o,m=f=>{u=Math.max(0,Math.min(100,(f.clientX-c.left-l)/c.width*100)),v=Math.max(0,Math.min(100,(f.clientY-c.top-d)/c.height*100)),t.style.left=`${u}%`,t.style.top=`${v}%`},p=()=>{t.removeEventListener("pointermove",m),t.removeEventListener("pointerup",p),t.removeEventListener("pointercancel",p),t.classList.remove("evcc-map-animal--dragging"),this.card._state.setRoomDotAnchor?.(n,u,v),this.card._scheduleRender()};t.addEventListener("pointermove",m),t.addEventListener("pointerup",p),t.addEventListener("pointercancel",p)})})},i._bindMapZoomPan=function(e){let t=e.querySelector(".evcc-map-container");if(!t)return;let r=()=>{let d=t.querySelector(".evcc-map-layers");if(!d)return;let u=this.card._state.mapZoom?.()??1,v=this.card._state.mapTranslateX?.()??0,m=this.card._state.mapTranslateY?.()??0;d.style.transform=`translate(${v}px,${m}px) scale(${u})`},a=!1,n=0,c=0,s=!1;t.addEventListener("pointerdown",d=>{if(d.button!==0||(this.card._mapDragOccurred=!1,d.target.closest("[data-action='map-dot-click']")))return;a=!0,s=!1,n=d.clientX,c=d.clientY;let u=m=>{if(!a)return;let p=m.clientX-n,f=m.clientY-c;n=m.clientX,c=m.clientY,!(!s&&Math.abs(p)<3&&Math.abs(f)<3)&&(s=!0,this.card._mapDragOccurred=!0,this.card._state.applyMapPan?.(p,f),r())},v=()=>{a=!1,document.removeEventListener("pointermove",u),document.removeEventListener("pointerup",v),document.removeEventListener("pointercancel",v)};document.addEventListener("pointermove",u),document.addEventListener("pointerup",v),document.addEventListener("pointercancel",v)}),t.addEventListener("dblclick",d=>{d.target.closest("[data-action='toggle-segment']")||(this.card._state.resetMapTransform?.(),r())});let o={},l=null;t.addEventListener("touchstart",d=>{Array.from(d.changedTouches).forEach(u=>{o[u.identifier]={x:u.clientX,y:u.clientY}}),Object.keys(o).length===2&&(d.preventDefault(),l=Ia(o))},{passive:!1}),t.addEventListener("touchmove",d=>{Array.from(d.changedTouches).forEach(h=>{o[h.identifier]={x:h.clientX,y:h.clientY}});let u=Object.values(o);if(u.length!==2||l===null)return;d.preventDefault();let v=Ia(o),m=t.getBoundingClientRect(),p=(u[0].x+u[1].x)/2-m.left,f=(u[0].y+u[1].y)/2-m.top;this.card._state.applyMapZoom?.((this.card._state.mapZoom?.()??1)*(v/l),p,f),r(),l=v},{passive:!1}),t.addEventListener("touchend",d=>{Array.from(d.changedTouches).forEach(u=>{delete o[u.identifier]}),Object.keys(o).length<2&&(l=null)})}}function Ia(i){let[e,t]=Object.values(i);return Math.sqrt((e.x-t.x)**2+(e.y-t.y)**2)}function Ai(i){return new Promise((e,t)=>{let r=new FileReader;r.onload=()=>{let a=r.result,n=a.indexOf(",");e(n>=0?a.slice(n+1):a)},r.onerror=t,r.readAsDataURL(i)})}function Ca(i){i._bindSetup=function(){let e=this.card;e._onAll("[data-action='setup-add-vacuum']","click",async()=>{let t=e._config?.vacuum_entity_id;if(t){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let r=await e._actions.addVacuum?.(t);e._state.setSetupLastResult?.(r);let a=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(a)}catch(r){e._state.setSetupError?.(`Failed to add vacuum: ${r?.message??String(r)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-import-map']","click",async()=>{let t=e._config?.vacuum_entity_id;if(t){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let r=await e._actions.importActiveMap?.(t);e._state.setSetupLastResult?.(r);let a=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(a);let c=(a?.vacuums?.find(s=>s.vacuum_entity_id===t)?.maps??[]).find(s=>s.imported&&!e._state.isSetupMapConfigured?.(String(s.map_id)));if(c){let s=String(c.map_id);e._state.setSetupRoomEditorLoadingMapId?.(s),e._state.setSetupError?.(null),e._scheduleRender();try{let o=await e._actions.getSetupMapRooms?.(t,s);e._state.openSetupRoomEditor?.(s,o?.rooms??[])}catch(o){e._state.setSetupError?.(`Failed to load rooms: ${o?.message??String(o)}`),e._state.setSetupRoomEditorLoadingMapId?.(null)}}}catch(r){e._state.setSetupError?.(`Failed to import map: ${r?.message??String(r)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-refresh']","click",async()=>{await e.refreshSetupStatus?.()}),e._onAll("[data-action='setup-configure-map']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!(!r||!a)){if(e._state.setupRoomEditorOpenMapId?.()===r){e._state.closeSetupRoomEditor?.(),e._scheduleRender();return}e._state.setSetupRoomEditorLoadingMapId?.(r),e._state.setSetupError?.(null),e._scheduleRender();try{let c=(await e._actions.getSetupMapRooms?.(a,r))?.rooms??[];e._state.openSetupRoomEditor?.(r,c)}catch(n){e._state.setSetupError?.(`Failed to load rooms: ${n?.message??String(n)}`),e._state.setSetupRoomEditorLoadingMapId?.(null)}e._scheduleRender()}}),e._onAll("[data-action='setup-toggle-room']","click",t=>{let r=t.currentTarget.dataset.roomId;r&&(e._state.toggleSetupRoom?.(r),e._scheduleRender())}),e._onAll("[data-action='setup-set-floor-type']","click",t=>{let r=t.currentTarget.dataset.roomId,a=t.currentTarget.dataset.floorType;!r||!a||(e._state.setSetupRoomFloorType?.(r,a),e._scheduleRender())}),e._onAll("[data-action='setup-save-rooms']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!(!r||!a)){e._state.setSetupRoomEditorSaving?.(!0),e._state.setSetupError?.(null),e._scheduleRender();try{let n=e._state.setupRoomEditorEnabledIds?.()??[],c=e._state.setupRoomEditorFloorTypesMap?.()??{};await e._actions.saveSetupRooms?.(a,r,n,c),e._state.markSetupMapConfigured?.(r),e._state.closeSetupRoomEditor?.();let s=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(s)}catch(n){e._state.setSetupError?.(`Failed to save rooms: ${n?.message??String(n)}`)}finally{e._state.setSetupRoomEditorSaving?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-delete-map-open']","click",t=>{let r=t.currentTarget.dataset.mapId,a=t.currentTarget.dataset.requiresTyped==="true";r&&(e._state.openSetupDeleteConfirm?.(r,a),e._scheduleRender())}),e._onAll("[data-action='setup-delete-map-cancel']","click",()=>{e._state.closeSetupDeleteConfirm?.(),e._scheduleRender()}),e._onAll("[data-action='setup-delete-map-input']","input",t=>{e._state.setSetupDeleteTypedToken?.(t.currentTarget.value),e._scheduleRender()}),e._onAll("[data-action='setup-delete-map-confirm']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!r||!a)return;let c=e._state.setupDeleteStage?.()==="typing"?e._state.setupDeleteTypedToken?.():"confirmed";e._state.setSetupDeleteDeleting?.(!0),e._state.setSetupError?.(null),e._scheduleRender();try{let s=await e._actions.deleteSetupMap?.(a,r,c);if(s?.status==="success"){e._state.closeSetupDeleteConfirm?.();let o=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(o)}else e._state.setSetupError?.(s?.message??"Failed to delete map."),e._state.setSetupDeleteDeleting?.(!1)}catch(s){e._state.setSetupError?.(`Failed to delete map: ${s?.message??String(s)}`),e._state.setSetupDeleteDeleting?.(!1)}finally{e._scheduleRender()}})}}function La(i){i._bindMappingReview=function(){this.card._onAll("[data-mrev-filter]","click",e=>{let t=e.currentTarget?.dataset?.mrevFilter;t&&(this.card._state.setMappingBoundsFilter?.(t),this.card._scheduleRender())}),this.card._onAll("[data-mrev-clear]","click",async e=>{let t=e.currentTarget?.dataset?.mrevClear;if(t){this.card._state.beginMappingBoundsClear?.(t),this.card._scheduleRender();try{await this.card._actions.clearRoomBounds?.({room_id:t}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingBoundsClear?.(),this.card._scheduleRender()}}}),this.card._onAll("[data-mrev-rebuild]","click",async e=>{let t=e.currentTarget?.dataset?.mrevRebuild;if(t){this.card._state.beginMappingRebuild?.(t),this.card._scheduleRender();try{await this.card._actions.rebuildRoomBoundsFromArchive?.({room_id:t}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingRebuild?.(),this.card._scheduleRender()}}}),this.card._onAll("[data-mrev-job-action]","click",async e=>{let t=e.currentTarget,r=t?.dataset?.mrevJobAction,a=t?.dataset?.mrevRoomId,n=t?.dataset?.mrevJobIndex;if(!(!r||!a||n==null)){this.card._state.beginMappingJobAction?.(a,Number(n),r),this.card._scheduleRender();try{r==="exclude"?await this.card._actions.excludeRoomJobBounds?.({room_id:a,job_index:Number(n)}):await this.card._actions.restoreRoomJobBounds?.({room_id:a,job_index:Number(n)}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingJobAction?.(),this.card._scheduleRender()}}})}}var G=class{constructor(e){this.card=e}sync(e){return this.card=e,this}bindEvents(){this._bindNav(),this._bindBaseStation(),this._bindMaintenance(),this._bindMetrics(),this._bindOrder(),this._bindRunProfiles(),this._bindReview(),this._bindRooms(),this._bindRoomAccess(),this._bindRoomEstimate(),this._bindRoomEditor(),this._bindRoomRules(),this._bindThemeEditor(),this._bindMap(),this._bindSetup(),this._bindMappingReview()}_bindOrder(){this.bindOrderEvents(this.card.shadowRoot)}bindModalHostEvents(e){if(!e)return;let t=e.querySelector("[data-stop-propagation]");t&&t.addEventListener("click",a=>a.stopPropagation()),e.querySelectorAll("[data-action='toggle-room']").forEach(a=>{a.addEventListener("click",async n=>{n.stopPropagation();let c=Number(a.dataset.roomId),s=String(a.dataset.mapId),o=a.dataset.enabled==="true";!c||!s||(await this.card._actions.toggleRoomEnabled(s,c,o),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='close-order-selector']").forEach(a=>{a.addEventListener("click",()=>{this.card._state.closeOrderSelector(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='set-order-position']").forEach(a=>{a.addEventListener("click",()=>{let n=Number(a.dataset.position);n&&(this.card._state.setOrderSelectorTargetPosition(n),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='confirm-order-selector']").forEach(a=>{a.addEventListener("click",async()=>{try{await this.confirmOrderSelectorWithFlip()}catch(n){console.error("[eufy-vacuum-command-center] Failed to save ordered position:",n)}})}),e.querySelectorAll("[data-action='open-order-selector']").forEach(a=>{a.addEventListener("click",()=>{let n=a.dataset.scope,c=a.dataset.itemId;!n||c==null||(this.card._state.openOrderSelector(n,c),this.card._scheduleRender())})}),this._bindMaintenanceModalHost?.(e),this._bindRoomAccessHost?.(e),this._bindRoomEstimateHost?.(e),e.querySelectorAll("[data-action='close-room-editor']").forEach(a=>{a.addEventListener("click",()=>{this.card._state.closeRoomEditor(),this.card._scheduleRender()})}),e.querySelectorAll("[data-field]").forEach(a=>{a.addEventListener("click",()=>{let n=a.dataset.field,c=a.dataset.value;if(!(!n||c===void 0)){if(a.dataset.action==="apply-profile"){this.card._state.applyEditorProfile(c),this.card._scheduleRender();return}n==="clean_passes"&&(c=Number(c)),n==="edge_mopping"&&(c=c==="true"),this.card._state.updateEditorField(n,c),this.card._scheduleRender()}})});let r=e.querySelector("[data-action='save-room-editor']");r&&r.addEventListener("click",async()=>{let a=this.card._state.activeEditorRoom(),n=this.card._state.editorFields();if(!(!a||!n))try{await this.card._actions.saveRoomEditor(a.mapId,a.id,n),await this._refreshRoomEditorEstimates?.(),this.card._state.closeRoomEditor(),this.card._scheduleRender()}catch(c){console.error("[eufy-vacuum-command-center] Failed to save room editor:",c)}}),e.querySelectorAll("[data-action='save-room-profile-as-new']").forEach(a=>{a.addEventListener("click",async()=>{await this._handleSaveRoomProfileAsNew?.()})}),e.querySelectorAll("[data-action='overwrite-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleOverwriteRoomProfile?.()})}),e.querySelectorAll("[data-action='rename-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleRenameRoomProfile?.()})}),e.querySelectorAll("[data-action='delete-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleDeleteRoomProfile?.()})})}};Vr(G.prototype);qr(G.prototype);Gr(G.prototype);Ur(G.prototype);Wr(G.prototype);Jr(G.prototype);Kr(G.prototype);Yr(G.prototype);Qr(G.prototype);Xr(G.prototype);Zr(G.prototype);ta(G.prototype);ka(G.prototype);Aa(G.prototype);Ca(G.prototype);La(G.prototype);function Pa(i){i.callService=async function(e,t,r={},a=!1){if(!this.hass?.callService)return console.warn("[eufy-vacuum-command-center] callService called before hass was ready.",{domain:e,service:t,data:r}),null;try{let n=await this.hass.callService(e,t,r,void 0,!1,a);return a?n:void 0}catch(n){return console.error(`[eufy-vacuum-command-center] ${e}.${t} failed`,{data:r,err:n}),null}},i.callHA=async function(e,t){return this.callService("homeassistant",e,{entity_id:t})},i.callNamedService=async function(e,t={},r=!1){let a=String(e??"").trim();if(!a||!a.includes("."))return console.warn("[eufy-vacuum-command-center] Invalid full service name",{fullService:e,data:t}),null;let[n,...c]=a.split("."),s=c.join(".");return!n||!s?(console.warn("[eufy-vacuum-command-center] Invalid split service name",{fullService:e,data:t}),null):this.callService(n,s,t,r)}}var Ci="get_dock_action_status",Li="wash_mop",Pi="dry_mop",Oi="stop_dry_mop",Ni="empty_dust";function Oa(i){i.getDockActionStatus=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let n=await this.callService(_,Ci,{vacuum_entity_id:r,map_id:String(a)},!0);return n?.response??n},i.washMop=async function(){return this._runDockAction(Li)},i.dryMop=async function(){return this._runDockAction(Pi)},i.stopDryMop=async function(){return this._runDockAction(Oi)},i.emptyDust=async function(){return this._runDockAction(Ni)},i._runDockAction=async function(e){let t=this.state?.vacuumEntityId?.(),r=this.state?.activeMapId?.();return!t||!r?null:this.callService(_,e,{vacuum_entity_id:t,map_id:String(r)})},i.getPauseTimeoutSettings=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(_,rt,{vacuum_entity_id:t},!0);return r?.response??r},i.setPauseTimeoutSettings=async function({vacuum_entity_id:e,pause_timeout_minutes_default:t}={}){let r=e??this.state?.vacuumEntityId?.();if(!r)return null;let a=await this.callService(_,at,{vacuum_entity_id:r,pause_timeout_minutes_default:Number(t)},!0);return a?.response??a}}var Fi="run_learning_estimate",Hi="reanchor_learning_timeline",Di="get_next_room",Bi="get_room_learning_estimates",ji="get_dashboard_snapshot",zi="get_incomplete_run_log",Vi="get_trouble_rooms_log";function Na(i){i.getDashboardSnapshot=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let n=await this.callService(_,ji,{vacuum_entity_id:r,map_id:String(a)},!0);return n?.response??n},i.runLearningEstimate=async function({vacuum_entity_id:e,map_id:t,current_battery:r,started_at:a}={}){let n=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.(),s=Number.isFinite(Number(r))?Number(r):this.state?.batteryLevel?.();if(!n||!c)return null;let o={vacuum_entity_id:n,map_id:String(c),current_battery:Number.isFinite(Number(s))?Number(s):0};a&&(o.started_at=String(a));let l=await this.callService(_,Fi,o,!0);return l?.response??l},i.reanchorLearningTimeline=async function({original_estimate:e,completed_rooms:t,reanchor_at:r,current_battery:a}={}){if(!e)return null;let n={original_estimate:e,completed_rooms:Array.isArray(t)?t:[],reanchor_at:r?String(r):new Date().toISOString()};if(a!=null){let s=Number(a);Number.isFinite(s)&&(n.current_battery=s)}let c=await this.callService(_,Hi,n,!0);return c?.response??c},i.getNextLearningRoom=async function({reanchored_estimate:e}={}){if(!e)return null;let t=await this.callService(_,Di,{reanchored_estimate:e},!0);return t?.response??t},i.getIncompleteRunLog=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(_,zi,{vacuum_entity_id:t},!0),a=r?.response??r;return!a||typeof a!="object"||!a.record_type?null:a},i.getTroubleRoomsLog=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(_,Vi,{vacuum_entity_id:t},!0),a=r?.response??r;return!a||typeof a!="object"||!a.record_type?null:a},i.getRoomLearningEstimates=async function({vacuum_entity_id:e,map_id:t,current_battery:r}={}){let a=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.();if(!a||!n)return null;let c={vacuum_entity_id:a,map_id:String(n)};if(r!=null){let o=Number(r);Number.isFinite(o)&&(c.current_battery=o)}let s=await this.callService(_,Bi,c,!0);return s?.response??s}}var qi="get_metrics_snapshot";function Fa(i){i.getMetricsSnapshot=async function({vacuum_entity_id:e,room_slug:t,profile_key:r,status:a,used_for_learning:n}={}){let c=e??this.state?.vacuumEntityId?.();if(!c)return null;let s={vacuum_entity_id:c};t&&(s.room_slug=String(t)),r&&(s.profile_key=String(r)),a&&(s.status=String(a)),typeof n=="boolean"&&(s.used_for_learning=n);let o=await this.callService(_,qi,s,!0);return o?.response??o}}function Ha(i){i.confirmOrderedPositionChange=async function(){let e=this.state.orderSelectorScope(),t=this.state.orderSelectorItemId(),r=this.state.orderSelectorTargetPosition(),a=this.state.getOrderAdapter(e);if(!a||t==null||r==null)return null;let n=this.state.previewMovedItemsForScope(e,t,r),c={scope:e,mode:"selector",itemId:t,targetPosition:r,patch:this.state._buildOrderPatch(n,a)};return await a.persist.call({_actions:this,state:this.state,hass:this.hass},n,c),this.state.closeOrderSelector(),{scope:e,movedItemId:t,mode:"selector"}},i.confirmDraggedOrderChange=async function(e,t){let r=this.state.getOrderAdapter(e),a=this.state.orderDragItemId();if(!r||a==null||t==null)return this.state.clearOrderDrag(),null;let n=this.state.previewDraggedItemsForScope(e,a,t),c={scope:e,mode:"drag",sourceId:a,targetId:t,patch:this.state._buildOrderPatch(n,r)};return await r.persist.call({_actions:this,state:this.state,hass:this.hass},n,c),this.state.clearOrderDrag(),{scope:e,movedItemId:a,mode:"drag"}}}function Da(i){i.getRoomProfiles=async function(){let e=await this.callService(_,it,{},!0);return e?.response??e??null},i.saveUserRoomProfile=async function(e={}){let t=await this.callService(_,nt,e,!0);return t?.response??t??null},i.saveRoomProfileFromRoom=async function({vacuum_entity_id:e,map_id:t,room_id:r,label:a,profile_name:n}={}){let c={vacuum_entity_id:e,map_id:t,room_id:r,label:a};n!=null&&String(n).trim()!==""&&(c.profile_name=String(n).trim());let s=await this.callService(_,ct,c,!0);return s?.response??s??null},i.overwriteRoomProfile=async function(e={}){let t=await this.callService(_,st,e,!0);return t?.response??t??null},i.overwriteRoomProfileFromRoom=async function({vacuum_entity_id:e,map_id:t,room_id:r,profile_name:a,label:n}={}){let c={vacuum_entity_id:e,map_id:t,room_id:r,profile_name:a};n!=null&&String(n).trim()!==""&&(c.label=String(n).trim());let s=await this.callService(_,ot,c,!0);return s?.response??s??null},i.renameRoomProfile=async function({profile_name:e,new_profile_name:t,label:r}={}){let a={profile_name:e};t!=null&&String(t).trim()!==""&&(a.new_profile_name=String(t).trim()),r!=null&&String(r).trim()!==""&&(a.label=String(r).trim());let n=await this.callService(_,lt,a,!0);return n?.response??n??null},i.deleteRoomProfile=async function({profile_name:e}={}){let t=await this.callService(_,dt,{profile_name:e},!0);return t?.response??t??null},i.applyRoomProfile=async function({vacuum_entity_id:e,map_id:t,room_ids:r,profile_name:a}={}){let n=Array.isArray(r)?r.map(s=>{if(typeof s=="number")return s;let o=String(s??"").trim();if(!o)return null;let l=Number(o);return Number.isNaN(l)?o:l}).filter(s=>s!=null):[],c=await this.callService(_,ut,{vacuum_entity_id:e,map_id:t,room_ids:n,profile_name:a},!0);return c?.response??c??null}}function Ba(i){i.getSavedRunProfiles=async function({vacuum_entity_id:e,map_id:t}={}){let r=await this.callService(_,vt,{vacuum_entity_id:e,map_id:t},!0);return r?.response??r},i.saveRunProfile=async function({vacuum_entity_id:e,map_id:t,name:r,expose_as_button:a}={}){let n=await this.callService(_,pt,{vacuum_entity_id:e,map_id:t,name:r,expose_as_button:!!a},!0);return n?.response??n},i.overwriteRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r,name:a,expose_as_button:n}={}){let c={vacuum_entity_id:e,map_id:t,profile_id:r};a!=null&&(c.name=a),n!=null&&(c.expose_as_button=!!n);let s=await this.callService(_,ht,c,!0);return s?.response??s},i.applyRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r}={}){let a=await this.callService(_,ft,{vacuum_entity_id:e,map_id:t,profile_id:r},!0);return a?.response??a},i.renameRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r,name:a}={}){let n=await this.callService(_,gt,{vacuum_entity_id:e,map_id:t,profile_id:r,name:a},!0);return n?.response??n},i.deleteRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r}={}){let a=await this.callService(_,_t,{vacuum_entity_id:e,map_id:t,profile_id:r},!0);return a?.response??a}}var Gi="get_learning_history_snapshot",Ui="exclude_learning_job",Wi="restore_learning_job";function ja(i){i.getLearningHistorySnapshot=async function({vacuum_entity_id:e,room_slug:t,profile_key:r,status:a,used_for_learning:n,limit:c}={}){let s=e??this.state?.vacuumEntityId?.();if(!s)return null;let o={vacuum_entity_id:s};t&&(o.room_slug=String(t)),r&&(o.profile_key=String(r)),a&&(o.status=String(a)),typeof n=="boolean"&&(o.used_for_learning=n),Number.isFinite(Number(c))&&(o.limit=Number(c));let l=await this.callService(_,Gi,o,!0);return l?.response??l},i.excludeLearningJob=async function({vacuum_entity_id:e,job_id:t,reason:r,rebuild_csv:a=!0}={}){let n=e??this.state?.vacuumEntityId?.();if(!n||!t)return null;let c=await this.callService(_,Ui,{vacuum_entity_id:n,job_id:String(t),...r?{reason:String(r)}:{},rebuild_csv:a!==!1},!0);return c?.response??c},i.restoreLearningJob=async function({vacuum_entity_id:e,job_id:t,rebuild_csv:r=!0}={}){let a=e??this.state?.vacuumEntityId?.();if(!a||!t)return null;let n=await this.callService(_,Wi,{vacuum_entity_id:a,job_id:String(t),rebuild_csv:r!==!1},!0);return n?.response??n}}function za(i){i.toggleRoomEnabled=async function(e,t,r){let a=this.state.findRoomSwitchEntityId(e,t);if(!a){console.warn(`[eufy-vacuum-command-center] Switch entity not found for room ${t} on map ${e}. Check that eufy_vacuum switch entities are loaded in HA. Available switches:`,this.state._findRoomSwitchEntities().map(n=>n.entityId));return}await this.callHA(r?"turn_off":"turn_on",a)},i.startCleaning=async function(e={}){let t=this.state.vacuumEntityId(),r=this.state.activeMapId();if(!t||!r)return;let a={vacuum_entity_id:t,map_id:r},n=await this.callService(_,et,a,!0),c=n?.response??n;if(c&&this.state.setStartStatus(c),c?.blocked)return this.state.clearStartConfirmation(),c;let s={vacuum_entity_id:t,map_id:r};e.confirmReducedRun&&(s.confirm_reduced_run=!0),e.confirmToken&&(s.confirm_token=e.confirmToken);let o=await this.callService(_,tt,s,!1),l=o?.response??o??{};if(l?.started===!1&&l?.reason==="confirmation_required")return this.state.setStartConfirmation(l?.preflight??c?.preflight??c??null,l?.confirm_token??null),l;if(l?.started===!1)return this.state.clearStartConfirmation(),l;this.state.clearStartConfirmation(),this.state.clearCancelRunConfirmation();let d=await this.runLearningEstimate({vacuum_entity_id:t,map_id:r,current_battery:this.state.batteryLevel()});if(this.state.setLearningEstimate(d??null),this.state.setLearningReanchored(null),this.state.setLearningCompletedRooms([]),this.state.setLearningNextRoom(null),this.state.setLearningJobActive(!1),this.state.beginLearningJob(),this.state.learningReanchored()){let u=await this.getNextLearningRoom({reanchored_estimate:this.state.learningReanchored()});this.state.setLearningNextRoom(u&&Object.keys(u).length?u:{})}return l??{started:!0}},i.retryMissedRooms=async function(e){if(!Array.isArray(e)||e.length===0)return;let t=this.state.getRoomsForActiveMap(),r=new Set(e.map(String));await Promise.all(t.map(a=>{let n=r.has(String(a.id));return n&&!a.enabled?this.toggleRoomEnabled(a.mapId,a.id,!1):!n&&a.enabled?this.toggleRoomEnabled(a.mapId,a.id,!0):Promise.resolve()}))},i.clearQueue=async function(){let e=this.state.vacuumEntityId(),t=this.state.activeMapId();if(!e||!t)return;let r=this.state.getRoomsForActiveMap();await Promise.all(r.filter(a=>a.enabled).map(a=>this.toggleRoomEnabled(a.mapId,a.id,!0))),await this.callService(_,Ze,{vacuum_entity_id:e,map_id:t}),this.state.clearStartConfirmation(),this.state.clearCancelRunConfirmation(),this.state.clearLearningJobContext()},i.selectAllRooms=async function(){let e=this.state.getRoomsForActiveMap();await Promise.all(e.filter(t=>!t.enabled).map(t=>this.toggleRoomEnabled(t.mapId,t.id,!1)))},i.deselectAllRooms=async function(){let e=this.state.getRoomsForActiveMap();await Promise.all(e.filter(t=>t.enabled).map(t=>this.toggleRoomEnabled(t.mapId,t.id,!0)))},i.refreshRoomLearningEstimates=async function(e={}){let t=e.vacuum_entity_id??this.state.vacuumEntityId(),r=e.map_id??this.state.activeMapId();if(!t||!r)return null;let a=await this.callService(_,"get_room_learning_estimates",{vacuum_entity_id:t,map_id:r},!0),n=a?.response??a??null;return n&&this.state.setRoomEstimates?.(n),n},i.updateRoomFields=async function(e,t={}){let r=this.state.vacuumEntityId(),a=this.state.activeMapId();if(!r||!a||e==null)return null;let n={...t};(n.water_level==null||String(n.water_level).trim()==="")&&delete n.water_level,(n.profile_name==null||String(n.profile_name).trim()==="")&&delete n.profile_name;let c={vacuum_entity_id:r,map_id:a,room_id:e,...n},s=await this.callService(_,mt,c,!0),o=s?.response??s??null;if(o)try{await this.refreshRoomLearningEstimates({vacuum_entity_id:r,map_id:a})}catch(l){console.warn("[eufy-vacuum-command-center] Failed to refresh room learning estimates after save",l)}return o},i.saveRoomEditor=async function(){let e=this.state.activeEditorRoom?.(),t=this.state.editorFields?.();if(!e||!t)return null;let r={clean_mode:t.clean_mode,fan_speed:t.fan_speed,clean_intensity:t.clean_intensity,clean_passes:t.clean_passes};return this.state.showWaterLevel()&&t.water_level!=null&&String(t.water_level).trim()!==""&&(r.water_level=t.water_level),this.state.showEdgeMopping()&&(r.edge_mopping=!!t.edge_mopping),this.updateRoomFields(e.id,r)},i.applyRoomProfile=async function(e,t){return this.updateRoomFields(e,{profile_name:t})},i.saveRoomTransition=async function(e,t){return this.updateRoomFields(e,{is_transition:t})},i.saveRoomAccess=async function(e,t,r){return this.updateRoomFields(e,{grants_access_to:t,is_dock_room:r})},i.cancelActiveRun=async function(){let e=this.state.vacuumEntityId();e&&(await this.callService("vacuum","return_to_base",{entity_id:e}),this.state.clearCancelRunConfirmation?.(),this.state.clearStartConfirmation?.())},i.persistRoomOrdering=async function(e){let t=this.state.activeMapId();!t||!Array.isArray(e)||await Promise.all(e.map(async(r,a)=>{let n=this.state.findRoomOrderNumberEntityId(t,r.id);n&&await this.callService("number","set_value",{entity_id:n,value:a+1})}))}}function Va(i){i._callThemeService=async function(e,t={}){return this.callService(_,e,t,!0)},i.getThemeLibrary=async function(){let e=await this._callThemeService(bt,{});return e?.response??e},i.setActiveTheme=async function(e,t){let r={theme_id:t};e&&(r.vacuum_entity_id=e);let a=await this._callThemeService(Rt,r);return a?.response??a},i.updateWorkingDraft=async function(e,{tokens:t,colors:r,alpha:a}={}){let n={vacuum_entity_id:e};t&&Object.keys(t).length&&(n.tokens=t),r&&Object.keys(r).length&&(n.colors=r),a&&Object.keys(a).length&&(n.alpha=a);let c=await this._callThemeService(Et,n);return c?.response??c},i.revertDraft=async function(e){let t=await this._callThemeService(kt,{vacuum_entity_id:e});return t?.response??t},i.saveThemeAsNew=async function(e,t,r=!1){let a=await this._callThemeService(yt,{vacuum_entity_id:e,name:t,set_as_default:!!r});return a?.response??a},i.overwriteTheme=async function(e,t){let r=await this._callThemeService(xt,{vacuum_entity_id:e,theme_id:t});return r?.response??r},i.renameTheme=async function(e,t){let r=await this._callThemeService(wt,{theme_id:e,name:t});return r?.response??r},i.deleteTheme=async function(e){let t=await this._callThemeService(St,{theme_id:e});return t?.response??t},i.exportTheme=async function(e){let t=await this._callThemeService(Tt,{theme_id:e});return t?.response??t},i.importTheme=async function(e){let t=await this._callThemeService($t,{payload:e});return t?.response??t}}function qa(i){i.getMapSegments=async function(e){let t=this.state.vacuumEntityId();if(!t||!e)return;let r=await this.callService(_,At,{vacuum_entity_id:t,map_id:e},!0),a=r?.response??r??null;a!=null&&this.state.setMapSegmentsData(a)},i.analyzeMapImage=async function(e,t={}){let r=this.state.vacuumEntityId();!r||!e||await this.hass.callService(_,It,{vacuum_entity_id:r,map_id:e,...t},void 0,!0)},i.uploadMapImage=async function(e,t,r={}){let a=this.state.vacuumEntityId();!a||!e||await this.hass.callService(_,Mt,{vacuum_entity_id:a,map_id:e,image_base64:t,...r},void 0,!0)},i.adjustMapSegment=async function(e,t,r={}){let a=this.state.vacuumEntityId();!a||!e||await this.hass.callService(_,Ct,{vacuum_entity_id:a,map_id:e,segment_id:t,...r},void 0,!0)},i.setSegmentRoomLink=async function(e,t,r){let a=this.state.vacuumEntityId();if(!a||!e||!t)return null;let n=await this.callService(_,Lt,{vacuum_entity_id:a,map_id:e,segment_id:t,room_id:r==null?null:String(r)},!0);return n?.response??n??null},i.setCompanionAnchor=async function(e,t,r,a){let n=this.state.vacuumEntityId();if(!n||!e||t==null)return null;let c={vacuum_entity_id:n,map_id:e,room_id:String(t)};r!=null&&(c.pct_x=Number(r)),a!=null&&(c.pct_y=Number(a));let s=await this.callService(_,Pt,c,!0);return s?.response??s??null}}function Ga(i){i.getSetupStatus=async function(){let e=await this.callService(_,Ot,{},!0);return e?.response??e??null},i.addVacuum=async function(e){let t=await this.callService(_,Nt,{vacuum_entity_id:e},!0);return t?.response??t??null},i.importActiveMap=async function(e){let t=await this.callService(_,Ft,{vacuum_entity_id:e},!0);return t?.response??t??null},i.getSetupMapRooms=async function(e,t){let r=await this.callService(_,Ht,{vacuum_entity_id:e,map_id:String(t)},!0);return r?.response??r??null},i.deleteSetupMap=async function(e,t,r){let a={vacuum_entity_id:e,map_id:String(t)};r&&(a.confirmation_token=r);let n=await this.callService(_,Bt,a,!0);return n?.response??n??null},i.saveSetupRooms=async function(e,t,r,a){let n=await this.callService(_,Dt,{vacuum_entity_id:e,map_id:String(t),enabled_room_ids:r,floor_types:a},!0);return n?.response??n??null}}var Ji="get_room_bounds_snapshot",Ki="clear_room_bounds",Yi="exclude_room_job_bounds",Qi="restore_room_job_bounds",Xi="rebuild_room_bounds_from_archive";function Ua(i){i.getMappingBoundsSnapshot=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let n=await this.callService(_,Ji,{vacuum_entity_id:r,map_id:String(a)},!0);return n?.response??n},i.clearRoomBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r}={}){let a=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.();if(!a||!n||!r)return null;let c=await this.callService(_,Ki,{vacuum_entity_id:a,map_id:String(n),room_id:String(r)},!0);return c?.response??c},i.excludeRoomJobBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r,job_index:a}={}){let n=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.();if(!n||!c||!r||a==null)return null;let s=await this.callService(_,Yi,{vacuum_entity_id:n,map_id:String(c),room_id:String(r),job_index:Number(a)},!0);return s?.response??s},i.restoreRoomJobBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r,job_index:a}={}){let n=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.();if(!n||!c||!r||a==null)return null;let s=await this.callService(_,Qi,{vacuum_entity_id:n,map_id:String(c),room_id:String(r),job_index:Number(a)},!0);return s?.response??s},i.rebuildRoomBoundsFromArchive=async function({vacuum_entity_id:e,map_id:t,room_id:r}={}){let a=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.();if(!a||!n||!r)return null;let c=await this.callService(_,Xi,{vacuum_entity_id:a,map_id:String(n),room_id:String(r)},!0);return c?.response??c}}var J=class{constructor(e,t){this.hass=e,this.state=t}sync(e,t){return this.hass=e,this.state=t,this}};Pa(J.prototype);Oa(J.prototype);Na(J.prototype);Fa(J.prototype);Ha(J.prototype);Da(J.prototype);Ba(J.prototype);ja(J.prototype);za(J.prototype);Va(J.prototype);qa(J.prototype);Ga(J.prototype);Ua(J.prototype);function Wa(i){i.$=function(e){return this.shadowRoot?.querySelector(e)??null},i.$all=function(e){return[...this.shadowRoot?.querySelectorAll(e)??[]]},i._on=function(e,t,r){e?.addEventListener(t,r)},i._onAll=function(e,t,r){this.$all(e).forEach(a=>a.addEventListener(t,r))}}var Ne=class{constructor(e){this.card=e,this._unsubRoomCompleted=null,this._unsubRoomStarted=null,this._unsubRoomFinished=null,this._unsubJobFinished=null,this._roomEstimateRequestSeq=0,this._lastRoomEstimateMapId=null,this._lastRoomEstimateVacuumEntityId=null,this._jobProgressResetTimer=null,this._boundsExitPollTimer=null,this._jobProgress={totalEstimatedMinutes:0,completedRoomMinutes:0,currentRoomStartedAt:null,currentRoomEstimatedMinutes:0,percent:0,ticker:null}}dismissLearningSummary(){let e=this.card?._state;e&&(e.clearLearningSummary(),this.card._scheduleRender())}connect(){this._unsubRoomCompleted||this._unsubRoomStarted||this._unsubRoomFinished||this._unsubJobFinished||!this.card?._hass?.connection?.subscribeEvents||(this._subscribeEvent("eufy_vacuum_room_completed","_unsubRoomCompleted",t=>this._handleRoomCompleted(t)),this._subscribeEvent("eufy_vacuum_room_started","_unsubRoomStarted",t=>this._handleRoomStarted(t)),this._subscribeEvent("eufy_vacuum_room_finished","_unsubRoomFinished",t=>this._handleRoomFinished(t)),this._subscribeEvent("eufy_vacuum_job_finished","_unsubJobFinished",t=>this._handleJobFinished(t)))}_subscribeEvent(e,t,r){let a=this.card?._hass;if(!a?.connection?.subscribeEvents)return;let n=a.connection.subscribeEvents(r,e);Promise.resolve(n).then(c=>{this[t]=typeof c=="function"?c:null}).catch(c=>{this[t]=null,console.warn(`[eufy-vacuum-command-center] Failed to subscribe to ${e}.`,c)})}disconnect(){typeof this._unsubRoomCompleted=="function"&&this._unsubRoomCompleted(),typeof this._unsubRoomStarted=="function"&&this._unsubRoomStarted(),typeof this._unsubRoomFinished=="function"&&this._unsubRoomFinished(),typeof this._unsubJobFinished=="function"&&this._unsubJobFinished(),this._unsubRoomCompleted=null,this._unsubRoomStarted=null,this._unsubRoomFinished=null,this._unsubJobFinished=null,this._stopBoundsExitPoll(),this._stopProgressTicker(),this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null)}async _handleRoomCompleted(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;if(!r||t.vacuum_entity_id!==r||!this.card?._state?.learningJobActive?.())return;let a=t.room_id,n=Number(t.duration_seconds);if(a==null||!Number.isFinite(n))return;this.card._state.pushCompletedLearningRoom({room_id:a,actual_duration_minutes:n/60}),this._jobProgress.completedRoomMinutes+=n/60,this._jobProgress.currentRoomStartedAt=Date.now();let s=(this.card._state.learningReanchored?.()?.room_timeline??this.card._state.learningEstimate?.()?.room_timeline)?.find(o=>!o.completed);this._jobProgress.currentRoomEstimatedMinutes=s?.minutes??0,await this._reanchorTimeline(),this._checkBoundsExitPolling()}async _handleRoomStarted(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(this._stopBoundsExitPoll(),await this.card?.refreshDashboardSnapshot?.(),this.card?._scheduleRender?.())}async _handleRoomFinished(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(this._stopBoundsExitPoll(),await this.card?.refreshDashboardSnapshot?.(),this._checkBoundsExitPolling(),this.card?._scheduleRender?.())}async _handleJobFinished(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(await this.card?.refreshDashboardSnapshot?.(),this.card?._state?.endLearningJob?.({duration_minutes:t.duration_minutes,actual_cleaning_minutes:t.actual_cleaning_minutes,room_count:t.room_count}),this.endJobProgress(),this.card?.refreshIncompleteRunLog?.(),this.card?.refreshTroubleRoomsLog?.(),this.card?._scheduleRender?.())}async _reanchorTimeline(){let e=this.card?._state,t=this.card?._actions;if(!e||!t)return;let r=e.learningEstimate();if(!r)return;let a=e.learningCompletedRooms(),n=e.batteryLevel(),c=await t.reanchorLearningTimeline({original_estimate:r,completed_rooms:a,reanchor_at:new Date().toISOString(),current_battery:Number.isFinite(n)?n:void 0});if(!c)return;e.setLearningReanchored(c),c?.total_minutes&&(this._jobProgress.totalEstimatedMinutes=c.total_minutes);let s=c?.room_timeline?.find(o=>!o.completed);this._jobProgress.currentRoomEstimatedMinutes=s?.minutes??0,await this._refreshNextRoom(),this.card._scheduleRender()}async _refreshNextRoom(){let e=this.card?._state,t=this.card?._actions;if(!e||!t)return;let r=e.learningReanchored();if(!r){e.setLearningNextRoom(null);return}let a=await t.getNextLearningRoom({reanchored_estimate:r});e.setLearningNextRoom(a&&Object.keys(a).length?a:{})}startJobProgress(e){if(!e)return;this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null),this._jobProgress.totalEstimatedMinutes=Number(e.total_minutes)||0,this._jobProgress.completedRoomMinutes=0,this._jobProgress.currentRoomStartedAt=Date.now();let t=e.room_timeline?.[0];this._jobProgress.currentRoomEstimatedMinutes=Number(t?.minutes)||0,this._jobProgress.percent=0,this._stopProgressTicker(),this._startProgressTicker()}endJobProgress(){this._stopProgressTicker(),this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null),this._jobProgress.percent=100,this.card._scheduleRender(),this._jobProgressResetTimer=setTimeout(()=>{this._jobProgress.percent=0,this._jobProgressResetTimer=null,this.card._scheduleRender()},3e3)}_checkBoundsExitPolling(){this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit?this._startBoundsExitPoll():this._stopBoundsExitPoll()}_startBoundsExitPoll(){this._boundsExitPollTimer||(this._boundsExitPollTimer=setInterval(async()=>{await this.card?.refreshDashboardSnapshot?.(),this.card?._scheduleRender?.(),this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit||this._stopBoundsExitPoll()},5e3))}_stopBoundsExitPoll(){this._boundsExitPollTimer&&(clearInterval(this._boundsExitPollTimer),this._boundsExitPollTimer=null)}_startProgressTicker(){this._jobProgress.ticker&&clearInterval(this._jobProgress.ticker),this._jobProgress.ticker=setInterval(()=>{this._jobProgress.percent=this._computeProgressPercent(),this.card._scheduleRender()},1e3)}_stopProgressTicker(){this._jobProgress.ticker&&(clearInterval(this._jobProgress.ticker),this._jobProgress.ticker=null)}_computeProgressPercent(){let e=this._jobProgress.totalEstimatedMinutes;if(!e||e<=0)return 0;let t=this._jobProgress.completedRoomMinutes,r=this._jobProgress.currentRoomStartedAt?Date.now()-this._jobProgress.currentRoomStartedAt:0,a=Math.max(0,r/6e4),n=Math.min(a,this._jobProgress.currentRoomEstimatedMinutes),s=(t+n)/e*100;return Math.min(Math.max(Math.floor(s),0),99)}getRoomProgressSnapshot(e){let t=this.card?._state?.learningTimelineEntryForRoom?.(e);if(t){let d=Number(t.progress_percent),u=Number(t.elapsed_minutes),v=Number(t.remaining_minutes),m=Number(t.minutes??(Number.isFinite(u)&&Number.isFinite(v)?u+v:null));if(Number.isFinite(d)||!!t.current||!!t.completed||!!t.remaining)return{isCompleted:!!t.completed,isCurrent:!!t.current,percent:t.completed?100:Number.isFinite(d)?Math.max(0,Math.min(99,Math.floor(d))):(t.current,0),elapsedMinutes:Number.isFinite(u)?u:0,estimatedMinutes:Number.isFinite(m)?m:null,remainingMinutes:t.completed?0:Number.isFinite(v)?v:Number.isFinite(m)?m:null}}let r=this.card._state.learningReanchored?.()?.room_timeline??this.card._state.learningEstimate?.()?.room_timeline??[],a=r.find(d=>String(d.room_id)===String(e));if(!a)return null;if(a.completed){let d=Number(a.actual_duration_minutes),u=Number(a.minutes);return{isCompleted:!0,isCurrent:!1,percent:100,elapsedMinutes:Number.isFinite(d)?d:u,estimatedMinutes:Number.isFinite(u)?u:null,remainingMinutes:0}}if(r.find(d=>!d.completed)?.room_id!==a.room_id)return{isCompleted:!1,isCurrent:!1,percent:0,elapsedMinutes:0,estimatedMinutes:Number(a.minutes)||null,remainingMinutes:Number(a.minutes)||null};let c=this._jobProgress.currentRoomStartedAt?Math.max(0,(Date.now()-this._jobProgress.currentRoomStartedAt)/6e4):0,s=Number(a.minutes)||1,o=Math.min(Math.max(Math.floor(c/s*100),0),99),l=Math.max(0,s-c);return{isCompleted:!1,isCurrent:!0,percent:o,elapsedMinutes:c,estimatedMinutes:s,remainingMinutes:l}}getJobProgressPercent(){let e=Number(this.card?._state?.dashboardJobProgress?.()?.progress_percent);return Number.isFinite(e)?Math.max(0,Math.min(100,e)):this._jobProgress.percent??0}getRoomProgressPercent(e){return this.getRoomProgressSnapshot(e)?.percent??0}async loadRoomEstimates(){let e=this.card?._state,t=this.card?._actions,r=this.card?._config;if(!e||!t||!r)return;let a=String(r.vacuum_entity_id??""),n=String(e.activeMapId?.()??"");if(!a||!n)return;(this._lastRoomEstimateVacuumEntityId!==a||this._lastRoomEstimateMapId!==n)&&(e.clearRoomEstimates(),this.card._scheduleRender()),this._lastRoomEstimateVacuumEntityId=a,this._lastRoomEstimateMapId=n;let s=++this._roomEstimateRequestSeq,o=null;try{o=await t.getRoomLearningEstimates({vacuum_entity_id:a,map_id:n,current_battery:e.batteryLevel?.()})}catch(m){if(s!==this._roomEstimateRequestSeq)return;console.warn("[eufy-vacuum-command-center] Failed to load room learning estimates.",m);return}if(s!==this._roomEstimateRequestSeq||!o)return;let l=String(this.card?._config?.vacuum_entity_id??""),d=String(this.card?._state?.activeMapId?.()??""),u=String(o.vacuum_entity_id??""),v=String(o.map_id??"");l===a&&d===n&&(u&&u!==a||v&&v!==n||(e.setRoomEstimates(o),this.card._scheduleRender()))}};var Fe=class i extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config=null,this._state=null,this._renderers=null,this._bindings=null,this._actions=null,this._view=b.ROOMS,this._renderScheduled=!1,this._deferredRenderTimer=null,this._startStatusTimer=null,this._dashboardSnapshotTimer=null,this._dockActionStatusTimer=null,this._pauseTimeoutSettingsTimer=null,this._metricsTimer=null,this._learningHistoryTimer=null,this._runProfilesTimer=null,this._incompleteRunLogTimer=null,this._incompleteRunLogLoaded=!1,this._troubleRoomsLogTimer=null,this._troubleRoomsLogLoaded=!1,this._themeLibrary={},this._modalHost=null,this._lastLoadedRoomEstimateMapId=null,this._lastLoadedRoomEstimateVacuumEntityId=null,this._themeLoaded=!1,this._setupStatusTimer=null,this._learningController=null,this._boundHandleVisibilityChange=()=>this._handleVisibilityChange(),this._boundHandlePanelResume=()=>this._handlePanelResume(),this._boundHandleLocationChanged=()=>this._handlePanelResume(),this._boundHandlePageShow=e=>{e.persisted&&this._handlePanelResume()},Wa(this)}setConfig(e){if(!e?.vacuum_entity_id)throw new Error("[eufy-vacuum-command-center] vacuum_entity_id is required in card config.");this._config=e,this._themeLibrary=e.theme_library??{},this._themeLoaded=!1,this._state?this._state.sync(this._hass,e):this._state=new D(this._hass,e),this._renderers||(this._renderers=new B(this)),this._actions?this._actions.sync?.(this._hass,this._state):this._actions=new J(this._hass,this._state),this._bindings||(this._bindings=new G(this)),this._learningController||(this._learningController=new Ne(this)),this._scheduleRender()}set panel(e){this._panel=e,e?.config?.vacuum_entity_id&&this.setConfig(e.config)}set narrow(e){this._narrow=e}set hass(e){if(this._hass=e,this._state&&this._state.sync(e,this._config),this._actions&&this._actions.sync?.(e,this._state),this._config?.vacuum_entity_id&&this._state){let t=this._findThemeSensor(e);t?.attributes&&this._state.setBackendThemeState?.(t.attributes)}this._scheduleRender(),this._scheduleStartStatusRefresh(),this._scheduleDashboardSnapshotRefresh(),this._scheduleDockActionStatusRefresh(),this._schedulePauseTimeoutSettingsRefresh(),this._scheduleMetricsRefresh(),this._scheduleLearningHistoryRefresh(),this._scheduleRunProfilesRefresh(),this._scheduleIncompleteRunLogRefresh(),this._scheduleTroubleRoomsLogRefresh(),this._loadInitialThemeState()}getCardSize(){return 6}static getStubConfig(){return{type:`custom:${De}`,vacuum_entity_id:"vacuum.your_vacuum"}}setView(e){e===b.MAPPING_ARCHIVE&&(e=b.ROOMS),this._view!==e&&(this._view=e,e===b.LEARNING_REVIEW&&this._scheduleLearningHistoryRefresh(),e===b.METRICS&&this._scheduleMetricsRefresh(),e===b.BASE_STATION&&(this._scheduleDockActionStatusRefresh(),this._schedulePauseTimeoutSettingsRefresh()),e===b.ROOMS&&this._scheduleRunProfilesRefresh(),e===b.SETUP&&this._scheduleSetupStatusRefresh(),e===b.MAPPING_REVIEW&&this._scheduleMappingBoundsRefresh(),this._scheduleRender())}_scheduleStartStatusRefresh(){!this._state||!this._actions||(clearTimeout(this._startStatusTimer),this._startStatusTimer=setTimeout(async()=>{let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return;let r=await this._actions.callService("eufy_vacuum","get_start_status",{vacuum_entity_id:e,map_id:t},!0),a=r?.response??r;a&&this._state&&(this._state._startStatus=a,this._scheduleRender())},800))}async refreshDashboardSnapshot(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getDashboardSnapshot({vacuum_entity_id:e,map_id:t});if(!r||!this._state)return null;this._state.setDashboardSnapshot?.(r);let a=r?.job_control??r?.start_status??null;return a&&(this._state._startStatus=a),this._scheduleRender(),r}_scheduleDashboardSnapshotRefresh(){!this._state||!this._actions||(clearTimeout(this._dashboardSnapshotTimer),this._dashboardSnapshotTimer=setTimeout(()=>{this.refreshDashboardSnapshot()},500))}async refreshDockActionStatus(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getDockActionStatus({vacuum_entity_id:e,map_id:t});return!r||!this._state?null:(this._state.setDockActionStatus?.(r),this._scheduleRender(),r)}async refreshPauseTimeoutSettings(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getPauseTimeoutSettings({vacuum_entity_id:e});return this._state.setPauseTimeoutSettings?.(t),this._scheduleRender(),t}_schedulePauseTimeoutSettingsRefresh(){!this._state||!this._actions||(clearTimeout(this._pauseTimeoutSettingsTimer),this._pauseTimeoutSettingsTimer=setTimeout(()=>{this.refreshPauseTimeoutSettings()},350))}_scheduleDockActionStatusRefresh(){!this._state||!this._actions||(clearTimeout(this._dockActionStatusTimer),this._dockActionStatusTimer=setTimeout(()=>{this.refreshDockActionStatus()},600))}async refreshMetricsSnapshot(){if(!this._state||!this._actions)return null;let e=this._state.metricsFilters?.()??{},t=await this._actions.getMetricsSnapshot({vacuum_entity_id:this._state.vacuumEntityId?.(),room_slug:e.room_slug||void 0,profile_key:e.profile_key||void 0,status:e.status||void 0,used_for_learning:e.used_for_learning==="true"?!0:e.used_for_learning==="false"?!1:void 0});return!t||!this._state?null:(this._state.setMetricsSnapshot?.(t),this._scheduleRender(),t)}_scheduleMetricsRefresh(){!this._state||!this._actions||this._view===b.METRICS&&(clearTimeout(this._metricsTimer),this._metricsTimer=setTimeout(()=>{this.refreshMetricsSnapshot()},500))}async refreshLearningHistorySnapshot(){if(!this._state||!this._actions)return null;let e=this._state.learningHistoryFilters?.()??{},t=await this._actions.getLearningHistorySnapshot({vacuum_entity_id:this._state.vacuumEntityId?.(),room_slug:e.room_slug||void 0,profile_key:e.profile_key||void 0,status:e.status||void 0,used_for_learning:e.used_for_learning==="true"?!0:e.used_for_learning==="false"?!1:void 0,limit:e.limit});return!t||!this._state?null:(this._state.setLearningHistorySnapshot?.(t),this._scheduleRender(),t)}_scheduleLearningHistoryRefresh(){!this._state||!this._actions||this._view===b.LEARNING_REVIEW&&(clearTimeout(this._learningHistoryTimer),this._learningHistoryTimer=setTimeout(()=>{this.refreshLearningHistorySnapshot()},500))}async refreshMappingBoundsSnapshot(){if(!this._state||!this._actions)return null;let e=await this._actions.getMappingBoundsSnapshot?.();return!e||!this._state?null:(this._state.setMappingBoundsSnapshot?.(e),this._scheduleRender(),e)}_scheduleMappingBoundsRefresh(){!this._state||!this._actions||this._view===b.MAPPING_REVIEW&&(clearTimeout(this._mappingBoundsTimer),this._mappingBoundsTimer=setTimeout(()=>{this.refreshMappingBoundsSnapshot()},500))}async refreshRunProfiles(){if(!this._state||!this._actions||this._view!==b.ROOMS)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getSavedRunProfiles({vacuum_entity_id:e,map_id:t});return this._state.setRunProfilesLibrary?.(r),this._scheduleRender(),r}async refreshRoomProfiles(){if(!this._state||!this._actions)return null;let e=await this._actions.getRoomProfiles();return e?(this._state.setRoomProfilesLibrary?.(e),this._scheduleRender(),e):null}_scheduleRunProfilesRefresh(){!this._state||!this._actions||this._view===b.ROOMS&&(clearTimeout(this._runProfilesTimer),this._runProfilesTimer=setTimeout(()=>{this.refreshRunProfiles()},450))}async refreshIncompleteRunLog(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getIncompleteRunLog?.({vacuum_entity_id:e});return this._incompleteRunLogLoaded=!0,this._state?(this._state.setIncompleteRunLog?.(t??null),this._scheduleRender(),t):null}_scheduleIncompleteRunLogRefresh(){!this._state||!this._actions||this._incompleteRunLogLoaded||(clearTimeout(this._incompleteRunLogTimer),this._incompleteRunLogTimer=setTimeout(()=>{this.refreshIncompleteRunLog()},1200))}async refreshTroubleRoomsLog(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getTroubleRoomsLog?.({vacuum_entity_id:e});return this._troubleRoomsLogLoaded=!0,this._state?(this._state.setTroubleRoomsLog?.(t??null),this._scheduleRender(),t):null}_scheduleTroubleRoomsLogRefresh(){!this._state||!this._actions||this._troubleRoomsLogLoaded||(clearTimeout(this._troubleRoomsLogTimer),this._troubleRoomsLogTimer=setTimeout(()=>{this.refreshTroubleRoomsLog()},1400))}async refreshSetupStatus(){if(!(!this._state||!this._actions)){this._state.setSetupLoading?.(!0),this._scheduleRender();try{let e=await this._actions.getSetupStatus?.();e&&this._state&&this._state.setSetupStatus?.(e)}finally{this._state.setSetupLoading?.(!1),this._scheduleRender()}}}_scheduleSetupStatusRefresh(){!this._state||!this._actions||this._view===b.SETUP&&(clearTimeout(this._setupStatusTimer),this._setupStatusTimer=setTimeout(()=>{this.refreshSetupStatus()},400))}_findThemeSensor(e){let t=this._config?.vacuum_entity_id;if(!t||!e)return null;let a=`sensor.${t.split(".")[1]}_theme_state`;return e.states[a]?e.states[a]:Object.values(e.states).find(n=>n.entity_id.startsWith("sensor.")&&n.entity_id.includes("_theme_state")&&n.attributes?.vacuum_entity_id===t)??null}async _loadInitialThemeState(){if(this._themeLoaded||!this._actions||!this._hass||!this._config?.vacuum_entity_id)return;let t=this._findThemeSensor(this._hass);t?.attributes&&this._state.setBackendThemeState?.(t.attributes);let r=await this._actions.getThemeLibrary();r&&this._state.setThemeLibrary?.(r),this._themeLoaded=!0,te(this),this._scheduleRender()}_scheduleRender(){this._renderScheduled||(this._renderScheduled=!0,Promise.resolve().then(()=>{this._renderScheduled=!1,this._render()}))}_scheduleDeferredRender(){this._deferredRenderTimer&&window.clearTimeout(this._deferredRenderTimer),this._deferredRenderTimer=window.setTimeout(()=>{this._deferredRenderTimer=null,this._scheduleRender()},600)}_render(){if(!this._config||!this._hass||!this._state||!this._renderers)return;te(this),this._maybeLoadRoomEstimates();let e=Ta(this),t=this._captureShadowFocusState(),r=this._captureShadowScrollState(),a=this._ensureShellFrame(wa),n=$a(e),c;try{c=Ma(e)}catch(o){console.error("[eufy-vacuum-command-center] renderView threw for view:",e.view,o),c=`<div class="evcc-empty">View error \u2014 check console (${e.view})</div>`}a.header.dataset.renderedHtml!==n&&(a.header.innerHTML=n,a.header.dataset.renderedHtml=n),a.viewStage.dataset.view=e.view,Object.entries(a.viewRoots).forEach(([o,l])=>{let d=o===e.view;l.hidden=!d,l.setAttribute("aria-hidden",d?"false":"true")});let s=a.viewRoots[e.view];s&&s.dataset.renderedHtml!==c&&(s.innerHTML=c,s.dataset.renderedHtml=c),this._updateModalHost(),this._bindings?.bindEvents(),this._restoreShadowFocusState(t),this._restoreShadowScrollState(r)}_ensureShellFrame(e){let t=this.shadowRoot?.querySelector("[data-evcc-style-root]"),r=this.shadowRoot?.querySelector("[data-evcc-header-root]"),a=this.shadowRoot?.querySelector("[data-evcc-view-stage]"),n=this._collectViewRoots();return!t||!r||!a||Object.keys(n).length!==Oe.length?(this.shadowRoot.innerHTML=`
        <style data-evcc-style-root>${e}</style>

        <ha-card>
          <div class="evcc-shell">
            <div data-evcc-header-root></div>
            <div class="evcc-view-stage" data-evcc-view-stage data-view="${this._view??b.ROOMS}">
              ${Oe.map(c=>`
                <div
                  class="evcc-view-root"
                  data-evcc-view-root="${c}"
                  ${c===(this._view??b.ROOMS)?"":"hidden"}
                  aria-hidden="${c===(this._view??b.ROOMS)?"false":"true"}"
                ></div>
              `).join("")}
            </div>
          </div>
        </ha-card>
      `,t=this.shadowRoot?.querySelector("[data-evcc-style-root]"),r=this.shadowRoot?.querySelector("[data-evcc-header-root]"),a=this.shadowRoot?.querySelector("[data-evcc-view-stage]"),n=this._collectViewRoots()):t.textContent!==e&&(t.textContent=e),{styleRoot:t,header:r,viewStage:a,viewRoots:n}}_collectViewRoots(){return this.shadowRoot?Oe.reduce((e,t)=>{let r=this.shadowRoot.querySelector(`[data-evcc-view-root="${t}"]`);return r instanceof HTMLElement&&(e[t]=r),e},{}):{}}_updateModalHost(){let e={state:this._state,renderers:this._renderers},t=typeof this._renderers.renderRoomEditorModal=="function"?this._renderers.renderRoomEditorModal(e):"",r=typeof this._renderers.renderRoomAccessModal=="function"?this._renderers.renderRoomAccessModal(e):"",a=typeof this._renderers.renderRoomEstimateModal=="function"?this._renderers.renderRoomEstimateModal(e):"",n=typeof this._renderers.renderOrderSelectorModal=="function"?this._renderers.renderOrderSelectorModal(e):"",c=typeof this._renderers.renderMaintenanceItemModal=="function"?this._renderers.renderMaintenanceItemModal(e):"",s=`${t}${r}${a}${n}${c}`;if(!s){this._modalHost&&(this._modalHost.remove(),this._modalHost=null);return}this._modalHost||(this._modalHost=document.createElement("div"),this._modalHost.className="evcc-modal-host",document.body.appendChild(this._modalHost));let o=`<style>${Sa}</style>${s}`;this._modalHost.dataset.renderedHtml!==o&&(this._modalHost.innerHTML=o,this._modalHost.dataset.renderedHtml=o),this._bindings?.bindModalHostEvents(this._modalHost)}connectedCallback(){this._learningController?.connect(),this._loadAnimalSvg(),document.addEventListener("visibilitychange",this._boundHandleVisibilityChange),window.addEventListener("focus",this._boundHandlePanelResume),window.addEventListener("location-changed",this._boundHandleLocationChanged),window.addEventListener("pageshow",this._boundHandlePageShow),this._scheduleRender()}_loadAnimalSvg(){i._animalSvgLoaded||(i._animalSvgLoaded=!0,import("/local/animal-svg/manifest.js").then(()=>this._scheduleRender()).catch(e=>console.warn("[eufy-vacuum-command-center] animal-svg load failed:",e)))}disconnectedCallback(){document.removeEventListener("visibilitychange",this._boundHandleVisibilityChange),window.removeEventListener("focus",this._boundHandlePanelResume),window.removeEventListener("location-changed",this._boundHandleLocationChanged),window.removeEventListener("pageshow",this._boundHandlePageShow),this._modalHost&&(this._modalHost.remove(),this._modalHost=null),this._learningController?.disconnect(),clearTimeout(this._startStatusTimer),clearTimeout(this._dashboardSnapshotTimer),clearTimeout(this._dockActionStatusTimer),clearTimeout(this._pauseTimeoutSettingsTimer),clearTimeout(this._metricsTimer),clearTimeout(this._learningHistoryTimer),clearTimeout(this._runProfilesTimer),clearTimeout(this._setupStatusTimer),clearTimeout(this._deferredRenderTimer),this._deferredRenderTimer=null}_handleVisibilityChange(){document.visibilityState==="visible"&&this._handlePanelResume()}_handlePanelResume(){this.offsetHeight,this._scheduleRender(),this._scheduleDashboardSnapshotRefresh(),this._scheduleStartStatusRefresh()}_maybeLoadRoomEstimates(){let e=this._state,t=this._learningController,r=this._config;if(!e||!t||!r)return;let a=String(e.activeMapId?.()??""),n=String(r.vacuum_entity_id??"");if(!a||!n||this._view!==b.ROOMS)return;let c=a===String(this._lastLoadedRoomEstimateMapId??""),s=n===String(this._lastLoadedRoomEstimateVacuumEntityId??"");c&&s||(t.loadRoomEstimates(),this._lastLoadedRoomEstimateMapId=a,this._lastLoadedRoomEstimateVacuumEntityId=n)}_captureShadowFocusState(){let e=this._getDeepActiveElement();if(!(e instanceof HTMLElement))return null;let t=this._buildFocusRestoreSelector(e);if(!t)return null;let r=e instanceof HTMLInputElement||e instanceof HTMLTextAreaElement;return{selector:t,selectionStart:r?e.selectionStart:null,selectionEnd:r?e.selectionEnd:null,selectionDirection:r?e.selectionDirection:null}}_getDeepActiveElement(){let e=document.activeElement;for(;e?.shadowRoot?.activeElement;)e=e.shadowRoot.activeElement;if(e instanceof HTMLElement&&this.shadowRoot?.contains(e))return e;let t=this.shadowRoot?.activeElement;return t instanceof HTMLElement?t:null}_restoreShadowFocusState(e){if(!e?.selector||!this.shadowRoot)return;let t=this.shadowRoot.querySelector(e.selector);if(!(!(t instanceof HTMLElement)||(t.focus({preventScroll:!0}),!(t instanceof HTMLInputElement||t instanceof HTMLTextAreaElement)))&&!(e.selectionStart==null||e.selectionEnd==null))try{t.setSelectionRange(e.selectionStart,e.selectionEnd,e.selectionDirection??"none")}catch{}}_buildFocusRestoreSelector(e){let t=["data-theme-search","data-theme-group-search","data-theme-token","data-theme-color-input","data-theme-alpha","data-rule-input","data-rule-select","data-rule-number-input","data-theme-modified-only","data-room-id","data-rule-id"];for(let r of t){if(!e.hasAttribute(r))continue;let a=e.getAttribute(r),n=String(e.tagName||"").toLowerCase(),c=e.getAttribute("type"),s=c?`[type="${CSS.escape(c)}"]`:"",o=Array.from(e.classList||[]).filter(Boolean).map(l=>`.${CSS.escape(l)}`).join("");return a==null||a===""?`${n}[${r}]${s}${o}`:`${n}[${r}="${CSS.escape(a)}"]${s}${o}`}return e.id?`#${CSS.escape(e.id)}`:null}_captureShadowScrollState(){return this.shadowRoot?[".evcc-view-stage",".evcc-theme-editor-scrollbox",".evcc-room-rules-content",".evcc-rule-editor-body",".evcc-rule-entity-search"].flatMap(t=>Array.from(this.shadowRoot.querySelectorAll(t)).map((r,a)=>({selector:t,index:a,scrollTop:r.scrollTop,scrollLeft:r.scrollLeft}))):[]}_restoreShadowScrollState(e=[]){!this.shadowRoot||!Array.isArray(e)||!e.length||e.forEach(t=>{let a=this.shadowRoot.querySelectorAll(t.selector)?.[t.index];a instanceof HTMLElement&&(a.scrollTop=t.scrollTop??0,a.scrollLeft=t.scrollLeft??0)})}};Fe._animalSvgLoaded=!1;customElements.define(De,Fe);var Ja="eufy-room-card",Xe="eufy-room-card-editor",Ye=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config={}}setConfig(e){this._config=e??{},this._render()}set hass(e){this._hass=e,this._render()}_vacuumEntities(){return this._hass?Object.keys(this._hass.states).filter(e=>e.startsWith("vacuum.")).sort():[]}_roomSwitchesFor(e){return!this._hass||!e?[]:Object.entries(this._hass.states).filter(([t,r])=>t.startsWith("switch.")&&r.attributes?.vacuum_entity_id===e&&r.attributes?.room_id!=null).map(([,t])=>({room_id:t.attributes.room_id,room_name:t.attributes.room_name??t.attributes.friendly_name??`Room ${t.attributes.room_id}`})).sort((t,r)=>String(t.room_name).localeCompare(String(r.room_name)))}_fire(e){!e?.vacuum_entity_id||e?.room_id==null||this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:e},bubbles:!0,composed:!0}))}_render(){let e=this._vacuumEntities(),t=this._config.vacuum_entity_id??"",r=this._roomSwitchesFor(t),a=this._config.room_id!=null?String(this._config.room_id):"",n=this._config.name??"";this.shadowRoot.innerHTML=`
      <style>
        :host { display: block; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
        label {
          font-size: 0.80rem; font-weight: 500;
          color: var(--secondary-text-color, #888);
          text-transform: uppercase; letter-spacing: 0.04em;
        }
        select, input {
          width: 100%; box-sizing: border-box; padding: 8px 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          border-radius: 6px;
          background: var(--card-background-color, #1c2127);
          color: var(--primary-text-color, #f0f2f5);
          font-size: 0.92rem; appearance: none; -webkit-appearance: none;
        }
        select:focus, input:focus { outline: none; border-color: var(--primary-color, #3b82f6); }
        .hint  { font-size: 0.75rem; color: var(--secondary-text-color, #888); margin-top: 2px; }
        .no-rooms {
          font-size: 0.85rem; color: var(--warning-color, #f59e0b);
          padding: 8px 10px; border: 1px solid currentColor; border-radius: 6px; opacity: 0.8;
        }
      </style>

      <div class="field">
        <label>Vacuum</label>
        <select id="vacuum">
          <option value="" disabled ${t?"":"selected"}>\u2014 pick a vacuum \u2014</option>
          ${e.map(c=>`<option value="${ce(c)}" ${c===t?"selected":""}>${ce(c)}</option>`).join("")}
        </select>
      </div>

      <div class="field">
        <label>Room</label>
        ${t?r.length===0?`<div class="no-rooms">No room switches found for ${ce(t)}.</div>`:`<select id="room">
               <option value="" disabled ${a?"":"selected"}>\u2014 pick a room \u2014</option>
               ${r.map(c=>`<option value="${ce(String(c.room_id))}" ${String(c.room_id)===a?"selected":""}>${ce(c.room_name)}</option>`).join("")}
             </select>`:'<div class="hint">Select a vacuum first.</div>'}
      </div>

      <div class="field">
        <label>Name override <span style="font-weight:400;text-transform:none">(optional)</span></label>
        <input id="name" type="text" placeholder="Leave blank to use room name" value="${ce(n)}">
        <div class="hint">Overrides the label shown on the card.</div>
      </div>
    `,this.shadowRoot.getElementById("vacuum")?.addEventListener("change",c=>{this._fire({...this._config,vacuum_entity_id:c.target.value,room_id:void 0})}),this.shadowRoot.getElementById("room")?.addEventListener("change",c=>{let s=c.target.value,o=Number(s);this._fire({...this._config,room_id:Number.isFinite(o)?o:s})}),this.shadowRoot.getElementById("name")?.addEventListener("change",c=>{let s=c.target.value.trim(),o={...this._config};s?o.name=s:delete o.name,this._fire(o)})}static getConfigElement(){return document.createElement(Xe)}static getStubConfig(e){let t=e?.states??{},r=Object.keys(t).find(n=>n.startsWith("vacuum."))??"",a=Object.entries(t).find(([n,c])=>n.startsWith("switch.")&&c.attributes?.vacuum_entity_id===r&&c.attributes?.room_id!=null);return{vacuum_entity_id:r,room_id:a?.[1]?.attributes?.room_id??null}}};customElements.define(Xe,Ye);var Qe=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config=null,this._fields=null,this._saving=!1,this._starting=!1}setConfig(e){this._config=e??{},this._fields=null,this._render()}set hass(e){this._hass=e,this._render()}_objectId(){return(this._config?.vacuum_entity_id??"").split(".")[1]??""}_allRoomSwitches(){let{states:e}=this._hass??{},t=this._config?.vacuum_entity_id;return!e||!t?[]:Object.entries(e).filter(([r,a])=>r.startsWith("switch.")&&a.attributes?.vacuum_entity_id===t&&a.attributes?.room_id!=null).map(([r,a])=>({entityId:r,state:a.state,attrs:a.attributes??{}}))}_targetSwitch(){let e=String(this._config?.room_id??"");return this._allRoomSwitches().find(t=>String(t.attrs.room_id)===e)??null}_optionsFrom(e,t){let a=this._hass?.states?.[e]?.attributes?.options;return Array.isArray(a)&&a.length?a:t}_cleanModeOptions(){return this._optionsFrom(`select.${this._objectId()}_cleaning_mode`,["Vacuum","Mop","Vacuum & Mop"])}_suctionOptions(){return this._optionsFrom(`select.${this._objectId()}_suction_level`,["Quiet","Standard","Turbo","Max"]).filter(e=>String(e).toLowerCase().replace(/[\s_-]/g,"")!=="boostiq")}_waterLevelOptions(){return this._optionsFrom(`select.${this._objectId()}_water_level`,["Low","Medium","High"]).filter(e=>String(e).toLowerCase()!=="off")}_cleanIntensityOptions(e,t){let r=this._objectId();return this._optionsFrom(`input_select.${r}_map_${t}_cleaning_speed_${e}`,["Quick","Normal","Narrow"])}_isMopMode(e){return String(e??"").toLowerCase().replace(/[\s_-]/g,"").includes("mop")}_committedFields(){let e=this._targetSwitch()?.attrs??{};return{clean_mode:e.clean_mode??"vacuum",fan_speed:e.fan_speed??null,water_level:e.water_level??null,clean_intensity:e.clean_intensity??null,clean_passes:Number(e.clean_passes??1),edge_mopping:!!(e.edge_mopping??!1)}}_currentFields(){return this._fields??this._committedFields()}_isDirty(){if(!this._fields)return!1;let e=this._committedFields();return Object.keys(this._fields).some(t=>this._fields[t]!==e[t])}_setField(e,t){this._fields={...this._currentFields(),[e]:t},this._render()}_render(){if(!this._config?.vacuum_entity_id||this._config?.room_id==null){this.shadowRoot.innerHTML="";return}let e=this._targetSwitch(),t=e?.attrs??{},r=e?.state==="on",a=this._config.name??t.room_name??`Room ${this._config.room_id}`,n=t.slug??"",c=String(t.map_id??""),s=!!(t.carpet??!1),o=this._currentFields(),l=this._isDirty(),d=this._isMopMode(o.clean_mode),u=this._cleanModeOptions(),v=this._suctionOptions(),m=d&&!s?this._waterLevelOptions():[],p=this._cleanIntensityOptions(n,c),f=d&&!s,h=(g,R,S,P)=>S.length?`
        <div class="field-group">
          <div class="field-label">${ce(g)}</div>
          <div class="chips">
            ${S.map(O=>`
              <button
                class="chip ${String(P??"").toLowerCase()===String(O).toLowerCase()?"active":""}"
                data-field="${ce(R)}"
                data-value="${ce(O)}"
              >${ce(O)}</button>
            `).join("")}
          </div>
        </div>
      `:"",y=()=>`
      <div class="field-group">
        <div class="field-label">Passes</div>
        <div class="chips">
          <button class="chip ${o.clean_passes===1?"active":""}" data-field="clean_passes" data-value="1">1 Pass</button>
          <button class="chip ${o.clean_passes===2?"active":""}" data-field="clean_passes" data-value="2">2 Passes</button>
        </div>
      </div>
    `,x=()=>f?`
      <div class="field-group">
        <div class="field-label">Edge Mopping</div>
        <div class="chips">
          <button class="chip ${o.edge_mopping?"active":""}" data-field="edge_mopping" data-value="true">On</button>
          <button class="chip ${o.edge_mopping?"":"active"}" data-field="edge_mopping" data-value="false">Off</button>
        </div>
      </div>
    `:"";this.shadowRoot.innerHTML=`
      <style>
        :host {
          display: block;
          --accent:       var(--evcc-accent, #3b82f6);
          --surface:      var(--evcc-surface-card, #1c2127);
          --border:       var(--evcc-border-default, rgba(255,255,255,0.10));
          --text-primary: var(--evcc-text-primary, #f0f2f5);
          --text-muted:   var(--evcc-text-muted, rgba(240,242,245,0.48));
          --radius:       var(--evcc-radius-card, 12px);
        }

        .card {
          background:   var(--surface);
          border:       1px solid var(--border);
          border-radius: var(--radius);
          overflow:     hidden;
        }

        /* ---- header ---- */
        .header {
          display:     flex;
          align-items: center;
          gap:         10px;
          padding:     14px 16px 12px;
          cursor:      pointer;
          user-select: none;
          -webkit-tap-highlight-color: transparent;
        }

        .indicator {
          width: 9px; height: 9px;
          border-radius: 50%; flex-shrink: 0;
          background: var(--border);
          transition: background 150ms ease;
        }

        .is-enabled .indicator {
          background: var(--accent);
          box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 60%, transparent);
        }

        .room-name {
          font-size: 0.96rem; font-weight: 700;
          color: var(--text-primary); flex: 1; min-width: 0;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }

        .dirty-badge {
          font-size: 0.70rem; font-weight: 600;
          color: var(--accent);
          background: color-mix(in srgb, var(--accent) 12%, transparent);
          border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
          border-radius: 4px; padding: 1px 6px;
          flex-shrink: 0;
        }

        /* ---- carpet notice ---- */
        .carpet-notice {
          margin: 0 16px 8px;
          font-size: 0.78rem;
          color: var(--text-muted);
          background: rgba(255,255,255,0.04);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 6px 10px;
        }

        /* ---- fields ---- */
        .fields {
          display: flex; flex-direction: column; gap: 12px;
          padding: 0 16px 14px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; }

        .field-label {
          font-size: 0.72rem; font-weight: 600;
          color: var(--text-muted);
          text-transform: uppercase; letter-spacing: 0.05em;
        }

        .chips { display: flex; flex-wrap: wrap; gap: 6px; }

        .chip {
          padding: 5px 12px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: rgba(255,255,255,0.04);
          color: var(--text-muted);
          font-size: 0.80rem; font-weight: 500;
          cursor: pointer;
          transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
          -webkit-tap-highlight-color: transparent;
        }

        .chip:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }

        .chip.active {
          background:   color-mix(in srgb, var(--accent) 18%, transparent);
          border-color: color-mix(in srgb, var(--accent) 50%, transparent);
          color:        color-mix(in srgb, var(--accent) 90%, white);
        }

        /* ---- footer ---- */
        .footer {
          display: flex; justify-content: flex-end; align-items: center; gap: 8px;
          padding: 10px 16px;
          border-top: 1px solid var(--border);
        }

        .btn {
          display: flex; align-items: center; gap: 6px;
          padding: 7px 16px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-muted);
          font-size: 0.82rem; font-weight: 600;
          cursor: pointer;
          transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
          -webkit-tap-highlight-color: transparent;
        }

        .btn:disabled { opacity: 0.4; cursor: default; }

        .btn-save {
          color: var(--accent);
          border-color: color-mix(in srgb, var(--accent) 40%, transparent);
          background: color-mix(in srgb, var(--accent) 8%, transparent);
        }

        .btn-save:hover:not(:disabled) {
          background: color-mix(in srgb, var(--accent) 18%, transparent);
        }

        .btn-start {
          color: #fff;
          border-color: transparent;
          background: var(--accent);
        }

        .btn-start:hover:not(:disabled) {
          background: color-mix(in srgb, var(--accent) 85%, white);
        }

        .btn-start:active:not(:disabled) { transform: scale(0.96); }

        @keyframes spin { to { transform: rotate(360deg); } }
        .spinning { animation: spin 0.9s linear infinite; display: inline-block; }
      </style>

      <div class="card">

        <div class="header ${r?"is-enabled":""}" role="button" aria-pressed="${r}" tabindex="0">
          <div class="indicator"></div>
          <span class="room-name">${ce(a)}</span>
          ${l?'<span class="dirty-badge">Unsaved</span>':""}
        </div>

        ${s?'<div class="carpet-notice">\u{1FAB5} Carpet room \u2014 mop fields hidden</div>':""}

        <div class="fields">
          ${h("Cleaning Mode","clean_mode",u,o.clean_mode)}
          ${h("Suction Level","fan_speed",v,o.fan_speed)}
          ${m.length?h("Water Level","water_level",m,o.water_level):""}
          ${h("Cleaning Path","clean_intensity",p,o.clean_intensity)}
          ${y()}
          ${x()}
        </div>

        <div class="footer">
          ${l?`
          <button class="btn btn-save" id="save-btn" ${this._saving?"disabled":""}>
            ${this._saving?'<span class="spinning">\u21BB</span> Saving\u2026':"Save"}
          </button>`:""}
          <button class="btn btn-start" id="start-btn" ${this._starting?"disabled":""}>
            ${this._starting?'<span class="spinning">\u21BB</span> Starting\u2026':'<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="margin-right:2px"><polygon points="5,3 19,12 5,21"/></svg> Start'}
          </button>
        </div>

      </div>
    `;let w=this.shadowRoot.querySelector(".header");w.addEventListener("click",()=>this._handleToggle()),w.addEventListener("keydown",g=>{(g.key==="Enter"||g.key===" ")&&(g.preventDefault(),this._handleToggle())}),this.shadowRoot.querySelectorAll(".chip").forEach(g=>{g.addEventListener("click",()=>{let{field:R,value:S}=g.dataset,P=S;R==="clean_passes"&&(P=Number(S)),R==="edge_mopping"&&(P=S==="true"),this._setField(R,P)})}),this.shadowRoot.getElementById("save-btn")?.addEventListener("click",()=>this._handleSave()),this.shadowRoot.getElementById("start-btn")?.addEventListener("click",()=>this._handleStart())}async _handleToggle(){if(!this._hass)return;let e=this._targetSwitch(),t=this._allRoomSwitches(),r=e?.state==="on";await Promise.all(t.filter(a=>a.state==="on").map(a=>this._hass.callService("switch","turn_off",{entity_id:a.entityId}))),!r&&e&&await this._hass.callService("switch","turn_on",{entity_id:e.entityId})}async _selectExclusive(){let e=this._targetSwitch(),t=this._allRoomSwitches();await Promise.all(t.filter(r=>r.state==="on").map(r=>this._hass.callService("switch","turn_off",{entity_id:r.entityId}))),e&&await this._hass.callService("switch","turn_on",{entity_id:e.entityId})}async _handleSave(){if(this._saving||!this._hass||!this._fields)return;let e=this._targetSwitch();if(e){this._saving=!0,this._render();try{await this._hass.callService("eufy_vacuum","update_room_fields",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id),room_id:this._config.room_id,...this._fields}),this._fields=null}finally{this._saving=!1,this._render()}}}async _handleStart(){if(this._starting||!this._hass)return;let e=this._targetSwitch();if(e){this._starting=!0,this._render();try{this._isDirty()&&(await this._hass.callService("eufy_vacuum","update_room_fields",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id),room_id:this._config.room_id,...this._fields}),this._fields=null),await this._selectExclusive(),await this._hass.callService("eufy_vacuum","start_selected_rooms",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id)})}finally{this._starting=!1,this._render()}}}static getConfigElement(){return document.createElement(Xe)}static getStubConfig(e){let t=e?.states??{},r=Object.keys(t).find(n=>n.startsWith("vacuum."))??"",a=Object.entries(t).find(([n,c])=>n.startsWith("switch.")&&c.attributes?.vacuum_entity_id===r&&c.attributes?.room_id!=null);return{vacuum_entity_id:r,room_id:a?.[1]?.attributes?.room_id??null}}};function ce(i){return String(i??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}customElements.define(Ja,Qe);window.customCards=window.customCards||[];window.customCards.push({type:Ja,name:"Eufy Room Card",description:"Single-room settings and quick-start card for Eufy vacuums"});
