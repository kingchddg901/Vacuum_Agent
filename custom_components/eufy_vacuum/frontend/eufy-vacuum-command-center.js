var nt="eufy-vacuum-command-center";var x="eufy_vacuum";var Ft="clear_queue";var Dt="get_start_status",Ht="start_selected_rooms";var zt="get_pause_timeout_settings",Bt="set_pause_timeout_settings",jt="get_room_profiles",Vt="save_user_room_profile",qt="save_room_profile_from_room",Gt="overwrite_room_profile",Ut="overwrite_room_profile_from_room",Wt="rename_room_profile",Jt="delete_room_profile",Kt="apply_room_profile",Yt="update_room_fields",Qt="get_saved_run_profiles",Xt="save_run_profile",Zt="overwrite_run_profile",er="apply_run_profile",tr="rename_run_profile",rr="delete_run_profile";var ar="get_theme_library",ir="save_theme_as_new",cr="overwrite_theme",nr="rename_theme",sr="set_theme_tags",or="delete_theme",lr="set_active_theme",dr="update_working_draft",ur="revert_draft",mr="export_theme",pr="import_theme",vr="upload_map_image",hr="delete_map_image",fr="analyze_map_image",gr="get_map_segments",br="adjust_map_segment",_r="set_segmentation_mode",yr="set_custom_segments",xr="create_custom_layout",wr="rename_custom_layout",Sr="delete_custom_layout",Rr="set_active_custom_layout",Er="set_segment_room_link",kr="set_companion_anchor",Tr="setup_get_status",$r="setup_add_vacuum",Mr="setup_import_active_map",Ar="setup_get_map_rooms",Cr="setup_save_rooms",Ir="setup_delete_map",Or="setup_reject_rooms",Lr="setup_force_remove_room",Pr="setup_set_panel_title";function Z(i){let e=String(i||"").split(".");return e.length>1?e[1]:e[0]}var Me={dockEvents:i=>`sensor.${Z(i)}_dock_events`,themeState:i=>`sensor.${Z(i)}_theme_state`,profileSensor:i=>`sensor.${Z(i)}_available_profiles`,activeMap:i=>`sensor.${Z(i)}_active_map`,robotPositionXRaw:i=>`sensor.${Z(i)}_robot_position_x_raw`,robotPositionYRaw:i=>`sensor.${Z(i)}_robot_position_y_raw`},We=new Set(["unknown","unavailable",""]);function Nr(i){i.entity=function(e){return e?this.hass?.states?.[e]??null:null},i.stateOf=function(e){return this.entity(e)?.state??null},i.attrsOf=function(e){return this.entity(e)?.attributes??{}},i.isValidState=function(e){return e==null?!1:!We.has(String(e))},i.hasEntity=function(e){let t=this.stateOf(e);return t!==null&&this.isValidState(t)},i.vacuumEntityId=function(){return this.config?.vacuum_entity_id??null},i.vacuumObjectId=function(){return Z(this.vacuumEntityId())},i.vacuumState=function(){let e=this.vacuumEntityId();return e?this.stateOf(e):null},i.vacuumStateLabel=function(){return this.dashboardLifecycle?.()?.vacuum_state_label??null},i.vacuumAttrs=function(){let e=this.vacuumEntityId();return e?this.attrsOf(e):{}},i.batteryLevel=function(){let e=this.vacuumAttrs()?.battery_level,t=Number(e);return Number.isFinite(t)?t:null},i.isCharging=function(){let e=this.vacuumObjectId();return e?this.stateOf(`binary_sensor.${e}_charging`)==="on":!1},i.batteryState=function(){if(this.isCharging())return"charging";let e=this.batteryLevel();return e==null?"good":e<=15?"low":e<=25?"warn":e<=50?"mid":"good"},i.vacuumDisplayName=function(){let e=this.vacuumAttrs();if(e?.friendly_name)return String(e.friendly_name).trim();let t=this.vacuumObjectId();return t?t.replace(/_/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Vacuum"},i.rawRobotPosition=function(){let e=this.vacuumEntityId();if(!e)return null;let t=Number(this.stateOf(Me.robotPositionXRaw(e))),r=Number(this.stateOf(Me.robotPositionYRaw(e)));return!Number.isFinite(t)||!Number.isFinite(r)?null:{x:Math.round(t),y:Math.round(r)}},i.attrOf=function(e,t,r=null){let c=this.attrsOf(e)?.[t];return c!==void 0?c:r}}function Fr(i){i._ensureDockState=function(){return this._dockState||(this._dockState={actionStatus:null,pendingAction:"",pauseTimeoutSettings:null}),this._dockState},i.setDockActionStatus=function(e){this._ensureDockState().actionStatus=e??null},i.dockActionStatus=function(){return this._ensureDockState().actionStatus??null},i.beginDockAction=function(e){this._ensureDockState().pendingAction=String(e??"")},i.endDockAction=function(){this._ensureDockState().pendingAction=""},i.pendingDockAction=function(){return this._ensureDockState().pendingAction??""},i.isDockActionPending=function(e){return this.pendingDockAction()===String(e??"")},i.dockActionGate=function(e){return this.dockActionStatus()?.actions?.[e]??null},i.dockActionAllowed=function(e){return this.dockActionGate(e)?.allowed===!0},i.dockStatus=function(){return this.dockActionStatus()?.dock_status??this.dashboardUpkeep?.()?.dock_status??null},i.dockStatusLabel=function(){return this.dockActionStatus()?.dock_status_label??this.dashboardUpkeep?.()?.dock_status_label??null},i.dockLifecycleState=function(){return this.dockActionStatus()?.lifecycle_state??null},i.dockLifecycleStateLabel=function(){return this.dockActionStatus()?.lifecycle_state_label??null},i.dockTaskStatus=function(){return this.dockActionStatus()?.task_status??this.dockActionStatus()?.active_job_status??null},i.dockTaskStatusLabel=function(){return this.dockActionStatus()?.task_status_label??this.dockActionStatus()?.active_job_status_label??null},i.isDocked=function(){return this.dockActionStatus()?.docked===!0},i.stationWaterLabel=function(){return this.dashboardUpkeep?.()?.station_water_label??null},i.setPauseTimeoutSettings=function(e){this._ensureDockState().pauseTimeoutSettings=e??null},i.pauseTimeoutSettings=function(){return this._ensureDockState().pauseTimeoutSettings??null},i.pauseTimeoutMinutesDefault=function(){let e=this.pauseTimeoutSettings?.(),t=Number(e?.pause_timeout_minutes_default);return Number.isFinite(t)?t:null}}var _e={LEARNING:"learning",ROOMS:"rooms",PROFILES:"profiles",WATER:"water",DOCK:"dock",BATTERY:"battery"};function Dr(i){i._ensureMetricsState=function(){return this._metricsState||(this._metricsState={snapshot:null,filters:{room_slug:"",profile_key:"",status:"",used_for_learning:""},activeTab:_e.LEARNING,pendingSaveKey:""}),this._metricsState},i.metricsSnapshot=function(){return this._ensureMetricsState().snapshot??null},i.setMetricsSnapshot=function(e){let t=this._ensureMetricsState();t.snapshot=e??null;let r=e?.filters;r&&typeof r=="object"&&(t.filters={room_slug:r.room_slug==null?"":String(r.room_slug),profile_key:r.profile_key==null?"":String(r.profile_key),status:r.status==null?"":String(r.status),used_for_learning:typeof r.used_for_learning=="boolean"?String(r.used_for_learning):""})},i.metricsFilters=function(){return this._ensureMetricsState().filters},i.setMetricsFilter=function(e,t){let r=this.metricsFilters();e in r&&(r[e]=t==null?"":String(t))},i.metricsActiveTab=function(){return this._ensureMetricsState().activeTab??_e.LEARNING},i.setMetricsActiveTab=function(e){let t=String(e??"").trim().toLowerCase();Object.values(_e).includes(t)&&(this._ensureMetricsState().activeTab=t)},i.metricsTabOptions=function(){return[{value:_e.LEARNING,label:"Learning"},{value:_e.ROOMS,label:"Rooms"},{value:_e.PROFILES,label:"Profiles"},{value:_e.WATER,label:"Water"},{value:_e.DOCK,label:"Dock"},{value:_e.BATTERY,label:"Battery"}]},i.metricsOverview=function(){return this.metricsSnapshot()?.overview??{}},i.metricsSelection=function(){return this.metricsSnapshot()?.selection??{}},i.metricsRooms=function(){return Array.isArray(this.metricsSnapshot()?.rooms)?this.metricsSnapshot().rooms:[]},i.metricsRoomProfiles=function(){return Array.isArray(this.metricsSnapshot()?.room_profiles)?this.metricsSnapshot().room_profiles:[]},i.metricsFoundProfiles=function(){return Array.isArray(this.metricsSnapshot()?.found_profiles)?this.metricsSnapshot().found_profiles:[]},i.metricsLearningStats=function(){return this.metricsSnapshot()?.room_learning_stats??{}},i.metricsSources=function(){return this.metricsSnapshot()?.sources??{}},i.beginMetricsProfileSave=function(e){this._ensureMetricsState().pendingSaveKey=String(e??"")},i.endMetricsProfileSave=function(){this._ensureMetricsState().pendingSaveKey=""},i.isMetricsProfileSavePending=function(e){return this._ensureMetricsState().pendingSaveKey===String(e??"")},i.metricsProfileSaveKey=function(e,t){let r=String(e??"profile"),a=String(t?.room_slug??""),c=String(t?.profile_key??"");return`${r}:${a}:${c}`},i.findMetricsSaveCandidate=function(e,t,r=""){let a=String(e??""),c=String(t??""),n=String(r??"");return c?(a==="found"?this.metricsFoundProfiles?.()??[]:this.metricsRoomProfiles?.()??[]).find(o=>String(o?.profile_key??"")===c&&String(o?.room_slug??"")===n)??null:null},i.metricsFilterRoomOptions=function(){let e=this.metricsSnapshot()?.filter_options?.rooms;return Array.isArray(e)&&e.length?e:[]},i._noteAmbiguousProfiles=function(e){this._ambiguousProfileLabels||(this._ambiguousProfileLabels=new Set);let t={};for(let r of e)t[String(r)]=(t[String(r)]||0)+1;for(let r in t)t[r]>1&&this._ambiguousProfileLabels.add(r)},i._isAmbiguousProfileLabel=function(e){return!!(this._ambiguousProfileLabels&&this._ambiguousProfileLabels.has(String(e)))},i._disambiguateProfileOptions=function(e){if(!Array.isArray(e)||!e.length)return Array.isArray(e)?e:[];let t=r=>String(r?.label??r?.value??r?.profile_key??"");return this._noteAmbiguousProfiles(e.map(t)),e.map(r=>{let a=t(r),c=String(r?.subtitle??"").trim();return this._isAmbiguousProfileLabel(a)&&c?{...r,label:`${a} \xB7 ${c}`}:r})},i.metricsFilterProfileOptions=function(){let e=this.metricsSnapshot()?.filter_options?.profiles;return Array.isArray(e)&&e.length?this._disambiguateProfileOptions(e):[]},i.metricsFilterStatusOptions=function(){let e=this.metricsSnapshot()?.filter_options?.statuses;return Array.isArray(e)&&e.length?e:[]},i.metricsFilterUsedOptions=function(){let e=this.metricsSnapshot()?.filter_options?.used_for_learning;return Array.isArray(e)&&e.length?e:[]},i._batterySensor=function(e){let t=this.vacuumObjectId();if(!t)return null;let r=`sensor.${t}_${e}`,a=this.stateOf(r);return a==null?null:{entity_id:r,state:a,attrs:this.attrsOf(r)??{}}},i.batteryMetrics=function(){return{cycles:this._batterySensor("charge_cycles"),health:this._batterySensor("battery_health"),rate_overall:this._batterySensor("charge_rate"),rate_low:this._batterySensor("charge_rate_low_zone"),rate_high:this._batterySensor("charge_rate_high_zone"),rate_mid_job:this._batterySensor("mid_job_recharge_rate"),last_charge_duration:this._batterySensor("last_charge_duration"),last_job_per_min:this._batterySensor("last_job_drain_rate")||this._batterySensor("last_job_drain_per_min"),last_job_per_hour:this._batterySensor("last_job_drain_per_hour"),last_job_per_m2:this._batterySensor("last_job_drain_per_m2")||this._batterySensor("last_job_drain_per_m_")}}}function Hr(i){i._ensureOrderState=function(){return this._orderState||(this._orderState={scope:null,activeItemId:null,targetPosition:null,dragItemId:null,dragOverItemId:null}),this._orderState},i.resetOrderState=function(){this._orderState={scope:null,activeItemId:null,targetPosition:null,dragItemId:null,dragOverItemId:null}},i._normalizeNumericOrder=function(e,t=999999){let r=Number(e);return Number.isFinite(r)?r:t},i._sortOrderedItems=function(e,t){let r=Array.isArray(e)?[...e]:[],a=t.getOrder,c=t.getId;return r.sort((n,s)=>{let o=this._normalizeNumericOrder(a(n)),l=this._normalizeNumericOrder(a(s));if(o!==l)return o-l;let d=String(c(n)),u=String(c(s));return d.localeCompare(u)})},i._reindexOrderedItems=function(e,t){let r=t.setOrder;return e.map((a,c)=>r(a,c+1))},i._moveOrderedItemToPosition=function(e,t,r,a){let c=this._reindexOrderedItems(this._sortOrderedItems(e,t),t),n=t.getId,s=Math.max(1,Math.min(Number(a)||1,c.length)),o=c.findIndex(u=>String(n(u))===String(r));if(o===-1)return c;let l=[...c],[d]=l.splice(o,1);return l.splice(s-1,0,d),this._reindexOrderedItems(l,t)},i._swapOrderedItemsById=function(e,t,r,a){let c=this._reindexOrderedItems(this._sortOrderedItems(e,t),t),n=t.getId,s=c.findIndex(u=>String(n(u))===String(r)),o=c.findIndex(u=>String(n(u))===String(a));if(s===-1||o===-1||s===o)return c;let l=[...c],[d]=l.splice(s,1);return l.splice(o,0,d),this._reindexOrderedItems(l,t)},i._buildOrderPatch=function(e,t){let r=t.getId,a=t.getOrder;return e.map(c=>({id:r(c),order:this._normalizeNumericOrder(a(c),1)}))},i.getOrderAdapter=function(e){return null},i.getOrderedItemsForScope=function(e){let t=this.getOrderAdapter(e);if(!t?.getItems)return[];let r=t.getItems.call(this);return this._reindexOrderedItems(this._sortOrderedItems(r,t),t)},i.getOrderedItemById=function(e,t){let r=this.getOrderedItemsForScope(e),a=this.getOrderAdapter(e);return a?r.find(c=>String(a.getId(c))===String(t))??null:null},i.getOrderedItemPosition=function(e,t){let r=this.getOrderedItemsForScope(e),a=this.getOrderAdapter(e);if(!a)return null;let c=r.findIndex(n=>String(a.getId(n))===String(t));return c===-1?null:c+1},i.openOrderSelector=function(e,t){let r=this._ensureOrderState(),a=this.getOrderedItemPosition(e,t);r.scope=e,r.activeItemId=t,r.targetPosition=a},i.closeOrderSelector=function(){let e=this._ensureOrderState();e.scope=null,e.activeItemId=null,e.targetPosition=null},i.isOrderSelectorOpen=function(){let e=this._ensureOrderState();return!!(e.scope&&e.activeItemId!=null)},i.orderSelectorScope=function(){return this._ensureOrderState().scope},i.orderSelectorItemId=function(){return this._ensureOrderState().activeItemId},i.orderSelectorItem=function(){let e=this._ensureOrderState();return!e.scope||e.activeItemId==null?null:this.getOrderedItemById(e.scope,e.activeItemId)},i.orderSelectorTargetPosition=function(){return this._ensureOrderState().targetPosition},i.setOrderSelectorTargetPosition=function(e){let t=this._ensureOrderState();t.targetPosition=Number(e)||1},i.orderSelectorPositions=function(){let e=this._ensureOrderState();if(!e.scope)return[];let t=this.getOrderedItemsForScope(e.scope);return Array.from({length:t.length},(r,a)=>a+1)},i.beginOrderDrag=function(e,t){let r=this._ensureOrderState();r.scope=e,r.dragItemId=t,r.dragOverItemId=t},i.setOrderDragOverItem=function(e){let t=this._ensureOrderState();t.dragOverItemId=e},i.orderDragItemId=function(){return this._ensureOrderState().dragItemId},i.orderDragOverItemId=function(){return this._ensureOrderState().dragOverItemId},i.clearOrderDrag=function(){let e=this._ensureOrderState();e.dragItemId=null,e.dragOverItemId=null},i.previewMovedItemsForScope=function(e,t,r){let a=this.getOrderAdapter(e);if(!a)return[];let c=a.getItems.call(this);return this._moveOrderedItemToPosition(c,a,t,r)},i.previewDraggedItemsForScope=function(e,t,r){let a=this.getOrderAdapter(e);if(!a)return[];let c=a.getItems.call(this);return this._swapOrderedItemsById(c,a,t,r)}}function zr(i){i._ensureRoomProfilesState=function(){return this._roomProfilesState||(this._roomProfilesState={profile_count:0,protected_profile_names:[],profiles:{}}),this._roomProfilesState},i._normalizeRoomProfile=function(e,t={}){return{name:String(e??""),label:String(t?.label??e??"Unnamed Profile"),clean_mode:String(t?.clean_mode??"vacuum"),fan_speed:String(t?.fan_speed??""),water_level:String(t?.water_level??""),clean_intensity:String(t?.clean_intensity??"Quick"),clean_passes:Number(t?.clean_passes??1),carpet:!!t?.carpet,edge_mopping:!!t?.edge_mopping}},i.setRoomProfilesLibrary=function(e){let t=this._ensureRoomProfilesState(),r=e?.profiles&&typeof e.profiles=="object"&&!Array.isArray(e.profiles)?e.profiles:{},a=Array.isArray(e?.protected_profile_names)?e.protected_profile_names.map(c=>String(c)):[];t.profile_count=Number(e?.profile_count??Object.keys(r).length??0),t.protected_profile_names=a,t.profiles=Object.fromEntries(Object.entries(r).map(([c,n])=>[String(c),this._normalizeRoomProfile(c,n)]).filter(([c])=>c))},i.roomProfilesLibrary=function(){return this._ensureRoomProfilesState().profiles},i.roomProfilesCount=function(){return this._ensureRoomProfilesState().profile_count??0},i.protectedRoomProfileNames=function(){return this._ensureRoomProfilesState().protected_profile_names??[]},i.isProtectedRoomProfile=function(e){let t=String(e??"").trim();return t?this.protectedRoomProfileNames().includes(t):!1},i.roomProfileDefinition=function(e){let t=String(e??"").trim();return t?this.roomProfilesLibrary()?.[t]??null:null},i.roomProfilesList=function(){let e=this.roomProfilesLibrary();return Object.values(e).sort((t,r)=>{let a=this.isProtectedRoomProfile(t.name),c=this.isProtectedRoomProfile(r.name);return a!==c?a?-1:1:String(t.label).localeCompare(String(r.label),void 0,{sensitivity:"base"})})},i.customRoomProfiles=function(){return this.roomProfilesList().filter(e=>!this.isProtectedRoomProfile(e.name))},i.makeRoomProfileName=function(e,t=null){let a=String(e??"").trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"").replace(/_+/g,"_"),c=a?`custom_${a}`:"custom_profile",n=String(t??"").trim();if(n&&n===c)return n;let s=new Set(Object.keys(this.roomProfilesLibrary()??{}));if(!s.has(c))return c;let o=2;for(;s.has(`${c}_${o}`);)o+=1;return`${c}_${o}`}}function Br(i){i._emptyRunProfileDraft=function(){return{name:"",expose_as_button:!1}},i._normalizeRunProfilesPayload=function(e){return Array.isArray(e)?{profiles:e,library:{}}:e&&typeof e=="object"?{profiles:Array.isArray(e.profiles)?e.profiles:Array.isArray(e.saved_run_profiles)?e.saved_run_profiles:[],library:e.library&&typeof e.library=="object"&&!Array.isArray(e.library)?e.library:{}}:{profiles:[],library:{}}},i._normalizeRunProfile=function(e){return{id:String(e?.id??e?.profile_id??""),name:String(e?.name??"Unnamed Profile"),vacuum_entity_id:String(e?.vacuum_entity_id??""),map_id:String(e?.map_id??""),room_count:Number(e?.room_count??0),room_ids:Array.isArray(e?.room_ids)?e.room_ids:[],room_names:Array.isArray(e?.room_names)?e.room_names:[],room_names_label:String(e?.room_names_label??""),expose_as_button:!!e?.expose_as_button,summary:String(e?.summary??""),created_at:String(e?.created_at??""),updated_at:String(e?.updated_at??""),rooms:Array.isArray(e?.rooms)?e.rooms:[]}},i._ensureRunProfilesState=function(){return this._runProfilesState||(this._runProfilesState={profiles:[],selectedProfileId:null,editorOpen:!1,editorMode:"new",editorProfileId:null,draft:this._emptyRunProfileDraft()}),this._runProfilesState},i.setRunProfilesLibrary=function(e){let t=this._ensureRunProfilesState(),r=this._normalizeRunProfilesPayload(e),a=r.profiles.map(c=>{let n=String(c?.id??c?.profile_id??""),s=n&&r.library?.[n]?r.library[n]:null;return this._normalizeRunProfile({...c,...s??{}})}).filter(c=>c.id);t.profiles=a,t.selectedProfileId&&!a.some(c=>c.id===t.selectedProfileId)&&(t.selectedProfileId=null),t.editorProfileId&&!a.some(c=>c.id===t.editorProfileId)&&(t.editorOpen=!1,t.editorMode="new",t.editorProfileId=null,t.draft=this._emptyRunProfileDraft())},i.savedRunProfiles=function(){return this._ensureRunProfilesState().profiles},i.savedRunProfilesCount=function(){return this.savedRunProfiles().length},i.selectedRunProfileId=function(){return this._ensureRunProfilesState().selectedProfileId??null},i.selectedRunProfile=function(){let e=this._ensureRunProfilesState();return e.profiles.find(t=>t.id===e.selectedProfileId)??null},i.selectRunProfile=function(e){let t=this._ensureRunProfilesState();t.selectedProfileId=e?String(e):null},i.openNewRunProfileEditor=function(){let e=this._ensureRunProfilesState();e.editorOpen=!0,e.editorMode="new",e.editorProfileId=null,e.draft=this._emptyRunProfileDraft()},i.openSelectedRunProfileEditor=function(){let e=this._ensureRunProfilesState(),t=this.selectedRunProfile();t&&(e.editorOpen=!0,e.editorMode="edit",e.editorProfileId=t.id,e.draft={name:t.name,expose_as_button:!!t.expose_as_button})},i.closeRunProfileEditor=function(){let e=this._ensureRunProfilesState();e.editorOpen=!1,e.editorMode="new",e.editorProfileId=null,e.draft=this._emptyRunProfileDraft()},i.isRunProfileEditorOpen=function(){return this._ensureRunProfilesState().editorOpen===!0},i.runProfileEditorMode=function(){return this._ensureRunProfilesState().editorMode??"new"},i.runProfileDraft=function(){return this._ensureRunProfilesState().draft},i.updateRunProfileDraft=function(e,t){let r=this._ensureRunProfilesState();if(e==="expose_as_button"){r.draft={...r.draft,expose_as_button:!!t};return}r.draft={...r.draft,[e]:t}}}var Ae={NEWEST:"newest",OUTLIER:"outlier",SUGGESTED:"suggested",EXCLUDED:"excluded"},jr="manual_test_run",Vr=Object.freeze({clean_mode:"Vacuum",fan_speed:"Standard",water_level:null,clean_intensity:"Quick",clean_passes:1,edge_mopping:!1});function qr(i){i._ensureReviewState=function(){return this._reviewState||(this._reviewState={snapshot:null,filters:{room_slug:"",profile_key:"",status:"",used_for_learning:"",limit:50},sort:Ae.NEWEST,excludeReasons:{},pendingJobActionId:"",matcherFields:{...Vr}}),this._reviewState},i.learningHistorySnapshot=function(){return this._ensureReviewState().snapshot??null},i.setLearningHistorySnapshot=function(e){let t=this._ensureReviewState();t.snapshot=e??null;let r=e?.filters;r&&typeof r=="object"&&(t.filters={room_slug:r.room_slug==null?"":String(r.room_slug),profile_key:r.profile_key==null?"":String(r.profile_key),status:r.status==null?"":String(r.status),used_for_learning:typeof r.used_for_learning=="boolean"?String(r.used_for_learning):"",limit:Number.isFinite(Number(r.limit))&&Number(r.limit)>0?Number(r.limit):t.filters?.limit??50})},i.learningHistoryFilters=function(){return this._ensureReviewState().filters},i.setLearningHistoryFilter=function(e,t){let r=this.learningHistoryFilters();if(e in r){if(e==="limit"){let a=Number(t);r[e]=Number.isFinite(a)&&a>0?a:50;return}r[e]=t==null?"":String(t)}},i.learningHistorySort=function(){return this._ensureReviewState().sort??Ae.NEWEST},i.setLearningHistorySort=function(e){let t=String(e??"").trim().toLowerCase();Object.values(Ae).includes(t)&&(this._ensureReviewState().sort=t)},i.learningHistoryJobs=function(){let e=this.learningHistorySnapshot()?.jobs;return Array.isArray(e)?e:[]},i.learningHistoryRooms=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.rooms;if(Array.isArray(e)&&e.length)return e.filter(n=>String(n?.value??"").trim()!=="").map(n=>({room_slug:String(n?.value??""),room_name:String(n?.label??n?.value??"")}));let t=this.learningHistorySnapshot?.(),r=Array.isArray(t?.rooms)?t.rooms:[],a=Array.isArray(t?.jobs)?t.jobs.flatMap(n=>Array.isArray(n?.room_slugs)?n.room_slugs.map(s=>({room_slug:s,room_name:this._formatReviewRoomLabel?.(s)??s})):[]):[],c=new Map;for(let n of[...r,...a]){let s=String(n?.room_slug??n?.slug??"").trim();s&&(c.has(s)||c.set(s,{room_slug:s,room_name:n?.room_name??n?.label??this._formatReviewRoomLabel?.(s)??s}))}return Array.from(c.values()).sort((n,s)=>String(n.room_name??n.room_slug).localeCompare(String(s.room_name??s.room_slug)))},i.learningHistoryProfiles=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.profiles;if(Array.isArray(e)&&e.length)return this._disambiguateProfileOptions(e.filter(n=>String(n?.value??"").trim()!=="").map(n=>({profile_key:String(n?.value??""),label:String(n?.label??n?.value??""),subtitle:n?.subtitle==null?null:String(n.subtitle),room_slug:n?.room_slug==null?null:String(n.room_slug),room_label:n?.room_label==null?null:String(n.room_label)})));let t=this.learningHistorySnapshot?.(),r=Array.isArray(t?.found_profiles)?t.found_profiles:[],a=Array.isArray(t?.room_profiles)?t.room_profiles:[],c=new Map;for(let n of[...r,...a]){let s=String(n?.profile_key??"").trim();s&&(c.has(s)||c.set(s,{profile_key:s,label:n?.profile_label??n?.label??n?.selected_profile_label??s,subtitle:n?.profile_subtitle??n?.resolved_profile_label??null}))}return this._disambiguateProfileOptions(Array.from(c.values()).sort((n,s)=>String(n.label??n.profile_key).localeCompare(String(s.label??s.profile_key))))},i.learningHistoryExcludeReason=function(e){return this._ensureReviewState().excludeReasons[String(e??"")]||jr},i.setLearningHistoryExcludeReason=function(e,t){this._ensureReviewState().excludeReasons[String(e??"")]=String(t??jr)},i.beginLearningHistoryJobAction=function(e){this._ensureReviewState().pendingJobActionId=String(e??"")},i.endLearningHistoryJobAction=function(){this._ensureReviewState().pendingJobActionId=""},i.isLearningHistoryJobActionPending=function(e){return this._ensureReviewState().pendingJobActionId===String(e??"")},i.learningHistorySortOptions=function(){return[{value:Ae.NEWEST,label:"Newest"},{value:Ae.OUTLIER,label:"Highest Outlier"},{value:Ae.SUGGESTED,label:"Suggested Exclude"},{value:Ae.EXCLUDED,label:"Excluded Only"}]},i.learningHistoryStatusOptions=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.statuses;return Array.isArray(e)&&e.length?e.map(t=>({value:String(t?.value??""),label:String(t?.label??t?.value??"")})):[{value:"",label:"All Statuses"},{value:"completed",label:"Completed"},{value:"canceled",label:"Canceled"},{value:"failed",label:"Failed"},{value:"interrupted",label:"Interrupted"}]},i.learningHistoryUsedOptions=function(){let e=this.learningHistorySnapshot?.()?.filter_options?.used_for_learning;return Array.isArray(e)&&e.length?e.map(t=>({value:String(t?.value_key??t?.value??""),label:String(t?.label??t?.value_key??t?.value??"")})):[{value:"",label:"All Learning Use"},{value:"true",label:"Used For Learning"},{value:"false",label:"Not Used For Learning"}]},i.learningHistoryExcludeReasonOptions=function(){return[{value:"short_test_cancel",label:"Short Test Cancel"},{value:"manual_test_run",label:"Manual Test Run"},{value:"false_completion",label:"False Completion"},{value:"bad_room_attribution",label:"Bad Room Attribution"},{value:"interrupted_run",label:"Interrupted Run"}]},i._formatReviewRoomLabel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())},i.reviewProfileMatcherFields=function(){return this._ensureReviewState().matcherFields},i.resetReviewProfileMatcher=function(){this._ensureReviewState().matcherFields={...Vr}},i.setReviewProfileMatcherField=function(e,t){let r=this.reviewProfileMatcherFields();if(!r||!(e in r))return;let a=t;if(e==="clean_mode"&&(a=this._canonicalCleanModeDisplay?.(t)??t),e==="clean_passes"){let c=Number(t);a=Number.isFinite(c)&&c>0?c:1}e==="edge_mopping"&&(a=t===!0||String(t??"").trim().toLowerCase()==="true"),r[e]=a,e==="clean_mode"&&!this.isMopMode?.(a)&&(r.water_level=null,r.edge_mopping=!1)},i.showReviewProfileMatcherWaterLevel=function(){let e=this.reviewProfileMatcherFields();return e?this.isMopMode?.(e.clean_mode)??!1:!1},i.showReviewProfileMatcherEdgeMopping=function(){let e=this.reviewProfileMatcherFields();return e?this.isMopMode?.(e.clean_mode)??!1:!1},i.reviewProfileMatcherCatalog=function(){let e=this.attrsOf?.(Me.profileSensor(this.vacuumEntityId()))??{},t=e.profiles??{},r=e.profile_labels??{},a=this.learningHistoryProfiles?.()??[],c=new Map(a.map(s=>[String(s?.profile_key??""),String(s?.label??s?.profile_key??"")]).filter(([s])=>s)),n=new Map;for(let[s,o]of Object.entries(t)){let l=String(s??"").trim();l&&(n.has(l)||n.set(l,{profile_key:l,label:c.get(l)||r[l]||l,definition:o}))}for(let s of a){let o=String(s?.profile_key??"").trim();!o||n.has(o)||n.set(o,{profile_key:o,label:String(s?.label??o),definition:null})}return Array.from(n.values()).sort((s,o)=>String(s.label??s.profile_key).localeCompare(String(o.label??o.profile_key)))},i.reviewProfileMatcherMatches=function(){let e=this.reviewProfileMatcherFields(),t=this.reviewProfileMatcherCatalog();return!e||!t.length?[]:t.filter(r=>r?.definition?this._editorFieldsMatchProfile?.(e,r.definition)===!0:!1)}}function Gr(i){i._normalizeRoomReferenceList=function(e){return e==null?[]:(Array.isArray(e)?e:[e]).map(r=>String(r??"").trim()).filter(r=>r!=="")},i._buildRoomAccessAdjacency=function(e=[]){let t={};return e.forEach(r=>{t[String(r.id)]=this._normalizeRoomReferenceList(r.grantsAccessTo)}),t},i._roomAccessGraphHasCycle=function(e={}){let t=new Set,r=new Set,a=c=>{if(r.has(c))return!0;if(t.has(c))return!1;t.add(c),r.add(c);let n=e[c]??[];for(let s of n)if(s in e&&a(s))return!0;return r.delete(c),!1};return Object.keys(e).some(c=>a(c))},i.roomAccessGraph=function(e=null){let t=e==null?this.getRoomsForActiveMap():this.getRoomsForMap(e),r=this._buildRoomAccessAdjacency(t);return t.map(a=>{let c=String(a.id),n=r[c]??[],s=t.filter(o=>(r[String(o.id)]??[]).includes(c)).map(o=>String(o.id));return{roomId:c,grantsAccessTo:n,requiresAccessFrom:s}})},i.validateRoomAccessUpdate=function(e,t,r=[]){let a=this.getRoomsForMap(e),c=String(t??"").trim(),n=new Set(a.map(h=>String(h.id))),s=this._normalizeRoomReferenceList(r),o=s.filter((h,b)=>s.indexOf(h)!==b),l=Array.from(new Set(s)),d=l.filter(h=>!n.has(h)),u=l.includes(c),m=[];n.has(c)||m.push({code:"missing_room",message:"This room no longer exists on the active map."}),u&&m.push({code:"self_reference",message:"A room cannot grant access to itself."}),o.length&&m.push({code:"duplicate_edges",message:"Each access link can only appear once.",roomIds:Array.from(new Set(o))}),d.length&&m.push({code:"missing_room_references",message:"All access links must point to rooms on the current map.",roomIds:d});let p=this._buildRoomAccessAdjacency(a),v=this._buildClaimedTargetMap(a,c),f=l.filter(h=>v.has(h)&&n.has(h));if(f.length){let h=Object.fromEntries(a.map(b=>[String(b.id),b.name]));f.forEach(b=>{let w=v.get(b),S=h[w]??`Room ${w}`,g=h[b]??`Room ${b}`;m.push({code:"multiple_inbound",message:`${g} already has an inbound link from ${S}. Each room can only be reached from one room.`,roomIds:[b,w].filter(Boolean)})})}return p[c]=l.filter(h=>n.has(h)),!m.length&&this._roomAccessGraphHasCycle(p)&&m.push({code:"cycle",message:"This access setup would create a loop in the room graph."}),{valid:m.length===0,issues:m,normalizedGrantsAccessTo:p[c]??[]}},i.orphanedRooms=function(e=null){let t=e!=null?this.getRoomsForMap(e):this.getRoomsForActiveMap();if(!t.some(c=>c.isDockRoom))return[];let a=new Set;return t.forEach(c=>{this._normalizeRoomReferenceList(c.grantsAccessTo).forEach(n=>{a.add(n)})}),t.filter(c=>c.isDockRoom?!1:!a.has(String(c.id)))},i._buildClaimedTargetMap=function(e=[],t=""){let r=new Map;return e.forEach(a=>{String(a.id)!==String(t)&&this._normalizeRoomReferenceList(a.grantsAccessTo).forEach(c=>{r.has(c)||r.set(c,String(a.id))})}),r},i.setStartStatus=function(e){this._startStatus=e??null},i.startPreflight=function(){let e=this.dashboardJobControl?.()?.preflight??this.dashboardStartStatus?.()?.preflight??this._startStatus?.preflight??null;if(e)return e;let t=this._startStatus??this.dashboardStartStatus?.()??null;return t?.selected_room_ids||t?.blocked_rooms||t?.modified_rooms?t:null},i.startMopCarpetWarning=function(){let e=this.startPreflight()?.mop_carpet_warning;return e?String(e):null},i.startOrderAdvisory=function(){let e=this.startPreflight()?.order_advisory;return e?String(e):null},i.setStartConfirmation=function(e=null,t=null){this._startConfirmation={preflight:e??this.startPreflight(),confirmToken:t??e?.confirm_token??null}},i.clearStartConfirmation=function(){this._startConfirmation=null},i.startConfirmation=function(){return this._startConfirmation??null},i.startRequiresConfirmation=function(){return!!(this._startConfirmation?.confirmToken||this._startConfirmation?.preflight?.requires_confirmation)},i.startConfirmationToken=function(){return this._startConfirmation?.confirmToken??this._startConfirmation?.preflight?.confirm_token??null},i.requestCancelRunConfirmation=function(){this.armConfirmation?.("rooms.cancel-run",{ttl:0,grace:700})},i.clearCancelRunConfirmation=function(){this.disarmConfirmation?.("rooms.cancel-run")},i.cancelRunRequiresConfirmation=function(){return this.isConfirmationArmed?.("rooms.cancel-run")===!0},i.cancelRunConfirmGuardActive=function(){return this.isConfirmationGuardActive?.("rooms.cancel-run")===!0},i.requestClearQueueConfirmation=function(){this.armConfirmation?.("rooms.clear-queue",{ttl:5e3,grace:700})},i.clearClearQueueConfirmation=function(){this.disarmConfirmation?.("rooms.clear-queue")},i.clearQueueRequiresConfirmation=function(){return this.isConfirmationArmed?.("rooms.clear-queue")===!0},i.clearQueueConfirmGuardActive=function(){return this.isConfirmationGuardActive?.("rooms.clear-queue")===!0},i.hasActiveRun=function(){let e=String(this.vacuumState()??"").toLowerCase();return e==="cleaning"||e==="paused"?!0:this._dashboardJobIsActive?.()??!1},i.shouldShowLiveQueue=function(){return(this.dashboardJobProgressTimeline?.()??[]).length>0&&this.hasActiveRun()},i.canPauseRun=function(){return String(this.vacuumState()??"").toLowerCase()==="cleaning"},i.canResumeRun=function(){return String(this.vacuumState()??"").toLowerCase()==="paused"},i.activeMapId=function(){let e=Me.activeMap(this.vacuumEntityId()),t=this.stateOf(e);if(t&&!We.has(String(t)))return String(t);let r=this._findRoomSwitchEntities();return r.length>0?String(r[0].attributes.map_id??"1"):"1"},i.queueChipLongPressMs=function(){let e=Number(this.config?.theme?.queue_chip_long_press_ms),t=Number(this.config?.queue_chip_long_press_ms),r=Number.isFinite(e)?e:Number.isFinite(t)?t:450;return Math.min(1e3,Math.max(250,r))},i._findRoomSwitchEntities=function(){let e=this.hass,t=this.vacuumEntityId();if(!e?.states||!t)return[];let r=[];for(let[a,c]of Object.entries(e.states)){if(!a.startsWith("switch."))continue;let n=c?.attributes;n&&n.vacuum_entity_id===t&&n.room_id!=null&&n.map_id!=null&&"enabled"in n&&r.push({entityId:a,state:c.state,attributes:n})}return r},i._findRoomOrderNumberEntities=function(){let e=this.hass,t=this.vacuumEntityId();if(!e?.states||!t)return[];let r=[];for(let[a,c]of Object.entries(e.states)){if(!a.startsWith("number."))continue;let n=c?.attributes;n&&n.vacuum_entity_id===t&&n.room_id!=null&&n.map_id!=null&&r.push({entityId:a,state:c.state,attributes:n})}return r},i.findRoomOrderNumberEntityId=function(e,t){let r=Object.values(this.hass?.states??{}),a=String(e),c=String(t),n=r.filter(o=>{if(!o?.entity_id?.startsWith("number."))return!1;let l=o.attributes??{};return String(l.map_id)===a&&String(l.room_id)===c});return n.find(o=>String(o.entity_id).toLowerCase().endsWith("_order"))?.entity_id??n[0]?.entity_id??null},i.findRoomSwitchEntityId=function(e,t){let r=this._findRoomSwitchEntities(),a=String(t),c=String(e);return r.find(s=>String(s.attributes.map_id)===c&&String(s.attributes.room_id)===a)?.entityId??null},i.getRoomsForActiveMap=function(){let e=this.activeMapId();return this.getRoomsForMap(e)},i.getRoomsForMap=function(e){let t=this._findRoomSwitchEntities(),r=this._findRoomOrderNumberEntities(),a={};for(let n of r){if(String(n.attributes.map_id)!==String(e))continue;let s=String(n.attributes.room_id),o=Number(n.state),l=String(n.entityId).toLowerCase().endsWith("_order");Number.isFinite(o)&&(!(s in a)||l)&&(a[s]=o)}let c=t.filter(n=>String(n.attributes.map_id)===String(e)).map(n=>{let s=String(n.attributes.room_id),o=n.state==="on",l=s in a?a[s]:n.attributes.order;return this._normalizeRoom(n.attributes,o,l)});return c.sort((n,s)=>{let o=(n.order??999)-(s.order??999);return o!==0?o:String(n.name).localeCompare(String(s.name))}),c},i._normalizeRoom=function(e,t,r=null){let a=Number(e.room_id),c=String(e.map_id??""),n=String(e.room_name??`Room ${e.room_id}`),s=e.slug??null,o=t!==void 0?!!t:!!e.enabled,l=Number(r??e.order??999),d=String(e.profile_name??"vacuum_quick"),u=e.profile_label??null,m=e.profile_subtitle??null,p=String(e.floor_type??""),v=e.floor_type_label??null,f=String(e.carpet_type??""),h=e.carpet_type_label??null,b=!!(e.carpet??(()=>{let Re=String(p).toLowerCase();return Re==="carpet"||Re.startsWith("carpet_")||Re.startsWith("carpet-")})()),w=e.clean_mode??"vacuum",S=e.fan_speed??null,g=e.water_level??null,R=e.clean_intensity??null,y=Number(e.clean_passes??1),T=!!(e.edge_mopping??!1),M=e.clean_mode_label??null,J=e.fan_speed_label??null,z=e.water_level_label??null,he=e.clean_intensity_label??e.path_type_label??null,B=e.clean_passes_label??null,Se=e.edge_mopping_label??null,ie=String(w??"").toLowerCase(),de=ie==="vacuum",fe=ie==="mop"||ie==="vacuum_mop"||ie.includes("mop")||ie.includes("wash"),ge=!!(e.is_dock_room??e.isDockRoom??!1),be=!!(e.is_transition??e.isTransition??!1),E=!!(e.transition_candidate??e.transitionCandidate??!1),q=Number(e.transition_score??e.transitionScore??0),U=this._normalizeRoomReferenceList(e.grants_access_to??e.grantsAccessTo),j=this._normalizeRoomReferenceList(e.requires_access_from??e.requiresAccessFrom),pe=e.rules??e.automation_rules,le=Array.isArray(pe)?pe:[],ce=e.last_cleaned_at??null,Le=e.last_vacuumed_at??null,Te=e.last_mopped_at??null,Pe=e.last_job_mode??null;return{id:a,mapId:c,name:n,slug:s,enabled:o,order:l,profileName:d,profileLabel:u,profileSubtitle:m,lastCleanedAt:ce,lastVacuumedAt:Le,lastMoppedAt:Te,lastJobMode:Pe,floorType:p,floorTypeLabel:v,carpetType:f,carpetTypeLabel:h,carpet:b,cleanMode:w,cleanModeLabel:M,fanSpeed:S,fanSpeedLabel:J,waterLevel:g,waterLevelLabel:z,cleanIntensity:R,cleanIntensityLabel:he,cleanPasses:y,cleanPassesLabel:B,edgeMopping:T,edgeMoppingLabel:Se,isCustomProfile:d.toLowerCase()==="custom",isVacuumOnly:de,isMopCapable:fe,isDockRoom:ge,isTransition:be,transitionCandidate:E,transitionScore:q,rules:le,profile:d,passes:y,grantsAccessTo:U,requiresAccessFrom:j,profile_name:d,floor_type:p,floor_type_label:v,carpet_type:f,carpet_type_label:h,clean_mode:w,clean_mode_label:M,fan_speed:S,fan_speed_label:J,water_level:g,water_level_label:z,clean_intensity:R,clean_intensity_label:he,clean_passes:y,clean_passes_label:B,edge_mopping:T,edge_mopping_label:Se,map_id:c,room_id:a,room_name:n,grants_access_to:U,requires_access_from:j,is_transition:be,transition_candidate:E,transition_score:q}},i._roomModeIncludesMop=function(e){let t=String(e??"").toLowerCase();return t==="mop"||t==="vacuum_mop"||t.includes("mop")||t.includes("wash")},i.enabledRoomCount=function(){return this.getRoomsForActiveMap().filter(e=>e.enabled).length},i._startStatusFlag=function(e){let t=this.dashboardJobControl?.()?.[e]??this.dashboardStartStatus?.()?.[e]??this._startStatus?.[e];if(typeof t=="boolean")return t;if(t==null)return!1;let r=String(t).trim().toLowerCase();return r==="true"||r==="1"||r==="yes"},i._localStartBlockReason=function(){if(this.enabledRoomCount()<1)return"No rooms included.";let e=String(this.vacuumState()??"").toLowerCase();return e==="cleaning"?"Already cleaning.":e==="returning"?"Returning to dock.":e==="error"?"Vacuum has an error.":null},i.canStartCleaning=function(){if(this._localStartBlockReason()&&!this.startRequiresConfirmation())return!1;let t=this.dashboardJobControl?.();return t&&t.can_start!=null?!!t.can_start:this._startStatus?!this._startStatusFlag("blocked"):!0},i.startBlockedReason=function(){if(this.startRequiresConfirmation())return null;let e=this._localStartBlockReason();if(e)return e;let t=this.dashboardJobControl?.();if(t){if(this._startStatusFlag("blocked"))return t.message??t.reason_detail??t.reason??"Start is blocked.";if(this._startStatusFlag("warning"))return t.message??t.reason_detail??null}return this._startStatus||this.dashboardStartStatus?.()?this._startStatusFlag("blocked")?this.dashboardStartStatus?.()?.message??this._startStatus?.message??"Start is blocked.":this._startStatusFlag("warning")?this.dashboardStartStatus?.()?.message??this._startStatus?.message??null:null:null},i.hasStartWarning=function(){return this._localStartBlockReason()?!1:this._startStatusFlag("warning")},i.startStatusReason=function(){return this.dashboardJobControl?.()?.reason??this.dashboardStartStatus?.()?.reason??this._startStatus?.reason??null},i.activeJobRooms=function(){let e=this.dashboardJobProgressTimeline?.()??[];if(this.shouldShowLiveQueue())return e.map((a,c)=>({jobOrder:a.position??c+1,name:a.room_name??`Room ${a.room_id??c+1}`}));let t=String(this.vacuumState()??"").toLowerCase();return new Set(["docked","idle","error"]).has(t)&&this._activeJobRooms?.length&&(this._activeJobRooms=null),this._activeJobRooms??null}}function Ur(i){i.getOrderAdapter=function(e){return e!=="rooms"?null:{scope:"rooms",getItems:function(){let t=this.getRoomsForActiveMap();return Array.isArray(t)?t:[]},getId:function(t){return t?.id},getLabel:function(t){return t?.name??"Room"},getOrder:function(t){return t?.order},setOrder:function(t,r){return{...t,order:r}},persist:async function(t,r={}){if(!this._actions?.persistRoomOrdering){console.warn("[eufy-vacuum-command-center] persistRoomOrdering not available");return}await this._actions.persistRoomOrdering(t,r)}}}}function Wr(i){i.openRoomAccess=function(e,t){let r=this.getRoomsForMap(t).find(a=>String(a.id)===String(e)&&String(a.mapId)===String(t));r&&(this._roomAccessRoomId=r.id,this._roomAccessMapId=r.mapId,this._roomAccessFields={is_dock_room:r.isDockRoom??!1,grants_access_to:[...r.grantsAccessTo??[]]},this._roomAccessSaveError=null)},i.closeRoomAccess=function(){this._roomAccessRoomId=null,this._roomAccessMapId=null,this._roomAccessFields=null,this._roomAccessSaveError=null},i.isRoomAccessOpen=function(){return this._roomAccessRoomId!=null},i.activeAccessRoom=function(){return!this._roomAccessRoomId||!this._roomAccessMapId?null:this.getRoomsForMap(this._roomAccessMapId).find(e=>String(e.id)===String(this._roomAccessRoomId)&&String(e.mapId)===String(this._roomAccessMapId))??null},i.roomAccessFields=function(){return this._roomAccessFields??{grants_access_to:[]}},i.setRoomAccessSaveError=function(e){this._roomAccessSaveError=e??null},i.roomAccessSaveError=function(){return this._roomAccessSaveError??null},i.accessEditableRooms=function(){let e=this.activeAccessRoom();if(!e)return[];let t=this.getRoomsForMap(e.mapId),r=new Set(this._normalizeRoomReferenceList(this.roomAccessFields().grants_access_to)),a=this._buildClaimedTargetMap(t,String(e.id)),c=t.filter(o=>{if(String(o.id)===String(e.id)||o.isDockRoom)return!1;let l=String(o.id),d=a.get(l);return r.has(l)||!d}).map(o=>({id:String(o.id),name:o.name,missing:!1,available:!0,claimedBy:null})),n=new Set(c.map(o=>o.id)),s=Array.from(r).filter(o=>!n.has(String(o))).map(o=>({id:String(o),name:`Missing Room ${o}`,missing:!0,available:!0,claimedBy:null}));return[...c,...s]},i.accessInboundRooms=function(){let e=this.activeAccessRoom();if(!e)return[];let t=this.getRoomsForMap(e.mapId),r=String(e.id);return t.filter(a=>this._normalizeRoomReferenceList(a.grantsAccessTo).includes(r)).map(a=>({id:String(a.id),name:a.name,missing:!1}))},i.toggleRoomAccessTarget=function(e){if(!this._roomAccessFields)return;let t=String(e??"").trim();if(!t)return;let r=new Set(this._normalizeRoomReferenceList(this._roomAccessFields.grants_access_to));r.has(t)?r.delete(t):r.add(t),this._roomAccessFields={...this._roomAccessFields,grants_access_to:Array.from(r)},this._roomAccessSaveError=null},i.toggleIsDockRoomField=function(){this._roomAccessFields&&(this._roomAccessFields={...this._roomAccessFields,is_dock_room:!this._roomAccessFields.is_dock_room},this._roomAccessSaveError=null)},i.roomAccessValidation=function(){let e=this.activeAccessRoom();return e?this.roomAccessFields().is_dock_room?{valid:!0,issues:[],normalizedGrantsAccessTo:[]}:this.validateRoomAccessUpdate(e.mapId,e.id,this.roomAccessFields().grants_access_to??[]):{valid:!1,issues:[{code:"missing_room",message:"No room is selected for access editing."}],normalizedGrantsAccessTo:[]}}}function Jr(i){i.openRoomEstimateModal=function(e,t){let r=this.getRoomsForMap(t).find(a=>String(a.id)===String(e)&&String(a.mapId)===String(t));r&&(this._roomEstimateModalRoomId=r.id,this._roomEstimateModalMapId=r.mapId)},i.closeRoomEstimateModal=function(){this._roomEstimateModalRoomId=null,this._roomEstimateModalMapId=null},i.isRoomEstimateModalOpen=function(){return this._roomEstimateModalRoomId!=null},i.activeRoomEstimateRoom=function(){return!this._roomEstimateModalRoomId||!this._roomEstimateModalMapId?null:this.getRoomsForMap(this._roomEstimateModalMapId).find(e=>String(e.id)===String(this._roomEstimateModalRoomId)&&String(e.mapId)===String(this._roomEstimateModalMapId))??null},i.activeRoomEstimateDetails=function(){let e=this.activeRoomEstimateRoom?.();if(!e)return null;let t=String(e.id),a=(Array.isArray(this.learningRoomTimeline?.())?this.learningRoomTimeline():[]).find(s=>String(s?.room_id)===t)??null,c=this.roomEstimateForRoom?.(e.id)??null,n=this.dashboardPlannedWaterRoomForRoom?.(e.id,e.slug)??null;return{room:e,entry:a,roomEstimate:c,plannedWaterRoom:n,confidenceBreakpoint:a?.confidence_breakpoint??c?.confidence_breakpoint??null,confidenceLabel:a?.confidence_label??c?.confidence_label??null}}}function Kr(i){i.openRoomEditor=function(e,t){let a=this.getRoomsForActiveMap().find(c=>String(c.id)===String(e)&&String(c.mapId)===String(t));a&&(this._roomEditorRoomId=a.id,this._roomEditorMapId=a.mapId,this._roomEditorFields={clean_mode:this._canonicalCleanModeDisplay(a.cleanMode??"vacuum"),fan_speed:a.fanSpeed??null,water_level:(()=>{let c=a.waterLevel??null;return String(c??"").trim().toLowerCase()==="off"?null:c})(),clean_intensity:a.cleanIntensity??a.selected_profile_details?.clean_intensity??"Quick",clean_passes:a.cleanPasses??1,edge_mopping:a.edgeMopping??!1,profile_name:a.profileName??"vacuum_quick"},this._syncEditorProfileFromFields())},i.closeRoomEditor=function(){this._roomEditorRoomId=null,this._roomEditorMapId=null,this._roomEditorFields=null,this._skipRefreshOnClose=!1},i.setSkipRefreshOnClose=function(e){this._skipRefreshOnClose=!!e},i.shouldSkipRefreshOnClose=function(){return!!this._skipRefreshOnClose},i.isRoomEditorOpen=function(){return this._roomEditorRoomId!=null},i.activeEditorRoom=function(){return this._roomEditorRoomId?this.getRoomsForActiveMap().find(t=>String(t.id)===String(this._roomEditorRoomId)&&String(t.mapId)===String(this._roomEditorMapId))??null:null},i.editorFields=function(){return this._roomEditorFields??null},i.availableEditorProfiles=function(){return this.roomProfilesLibrary?.()??{}},i.editorProfileLabels=function(){return Object.fromEntries(this.roomProfilesList?.().map(e=>[e.name,e.label])??[])},i.getEditorProfileDefinition=function(e){return this.roomProfileDefinition?.(e)??null},i._profileDerivedOptions=function(e){let t=this.availableEditorProfiles(),r=new Set;return Object.values(t).forEach(a=>{let c=a?.[e];c!=null&&String(c).trim()!==""&&r.add(String(c))}),Array.from(r)},i._normalizeOptionList=function(e){let t=new Set,r=[];for(let a of e??[]){let c=String(a??"").trim();if(!c)continue;let n=c.toLowerCase();t.has(n)||(t.add(n),r.push(c))}return r},i._canonicalCleanModeDisplay=function(e){let t=String(e??"").trim(),r=t.toLowerCase().replace(/[\s+_-]+/g,"");return r==="vacuummop"||r==="vacuumandmop"?"Vacuum and mop":r==="vacuum"?"Vacuum":r==="mop"?"Mop":t},i._canonicalCleanModeCompare=function(e){let t=String(e??"").trim().toLowerCase().replace(/[\s+_-]+/g,"");return t==="vacuummop"||t==="vacuumandmop"?"vacuum_mop":t==="vacuum"?"vacuum":t==="mop"?"mop":t},i._profileIntensityToEditorIntensity=function(e){let t=String(e??"").trim().toLowerCase();return t==="quick"?"Quick":t==="deep"?"Narrow":e??null},i._editorIntensityToComparableProfileIntensity=function(e){let t=String(e??"").trim().toLowerCase();return t==="quick"?"quick":t==="narrow"?"deep":t},i._normalizeEditorComparisonValue=function(e,t=""){if(t==="clean_mode")return this._canonicalCleanModeCompare(e);if(t==="clean_intensity")return this._editorIntensityToComparableProfileIntensity(e);if(e==null)return null;if(typeof e=="boolean")return e;if(typeof e=="number")return Number(e);let r=String(e).trim(),a=r.toLowerCase();if(a==="true")return!0;if(a==="false")return!1;let c=Number(r);return!Number.isNaN(c)&&r!==""?c:a},i._buildComparableProfileFields=function(e){let t=this.isEditorRoomCarpet(),r=this._canonicalCleanModeDisplay(e?.clean_mode??"vacuum"),a=this.isMopMode(r)&&!t;return{clean_mode:r,fan_speed:e?.fan_speed??null,water_level:a?e?.water_level??null:null,clean_intensity:this._profileIntensityToEditorIntensity(e?.clean_intensity??null),clean_passes:Number(e?.clean_passes??1),edge_mopping:a?!!e?.edge_mopping:!1}},i._editorFieldsMatchProfile=function(e,t){if(!e||!t)return!1;let r=this._buildComparableProfileFields(t);return this._normalizeEditorComparisonValue(e.clean_mode,"clean_mode")===this._normalizeEditorComparisonValue(r.clean_mode,"clean_mode")&&this._normalizeEditorComparisonValue(e.fan_speed)===this._normalizeEditorComparisonValue(r.fan_speed)&&this._normalizeEditorComparisonValue(e.water_level)===this._normalizeEditorComparisonValue(r.water_level)&&this._normalizeEditorComparisonValue(e.clean_intensity,"clean_intensity")===this._normalizeEditorComparisonValue(r.clean_intensity,"clean_intensity")&&this._normalizeEditorComparisonValue(e.clean_passes)===this._normalizeEditorComparisonValue(r.clean_passes)&&this._normalizeEditorComparisonValue(e.edge_mopping)===this._normalizeEditorComparisonValue(r.edge_mopping)},i.matchingEditorProfileName=function(e=null){let t=e??this.editorFields();if(!t)return null;let r=this.availableEditorProfiles();for(let[a,c]of Object.entries(r))if(this._editorFieldsMatchProfile(t,c))return a;return null},i._syncEditorProfileFromFields=function(){if(!this._roomEditorFields)return;let e=this.matchingEditorProfileName(this._roomEditorFields);this._roomEditorFields={...this._roomEditorFields,profile_name:e??"custom"}},i.applyEditorProfile=function(e){if(!this._roomEditorFields)return;let t=this.getEditorProfileDefinition(e);if(!t)return;let r=this._canonicalCleanModeDisplay(t.clean_mode??this._roomEditorFields.clean_mode??"vacuum"),a=this.isEditorRoomCarpet(),c=this.isMopMode(r)&&!a;this._roomEditorFields={...this._roomEditorFields,profile_name:String(e),clean_mode:r,fan_speed:t.fan_speed??null,water_level:c?t.water_level??null:null,clean_intensity:this._profileIntensityToEditorIntensity(t.clean_intensity??null),clean_passes:Number(t.clean_passes??1),edge_mopping:c?!!t.edge_mopping:!1}},i.updateEditorField=function(e,t){if(!this._roomEditorFields)return;if(e==="profile_name"){t==="custom"?this._roomEditorFields={...this._roomEditorFields,profile_name:"custom"}:this.applyEditorProfile(t);return}let r=e==="clean_mode"?this._canonicalCleanModeDisplay(t):t;this._roomEditorFields={...this._roomEditorFields,[e]:r},e==="clean_mode"&&!this.isMopMode(r)&&(this._roomEditorFields.water_level=null,this._roomEditorFields.edge_mopping=!1),e==="clean_mode"&&this.isEditorRoomCarpet()&&(this._roomEditorFields.water_level=null,this._roomEditorFields.edge_mopping=!1),this._syncEditorProfileFromFields()},i.isMopMode=function(e){let t=this._canonicalCleanModeCompare(e);return t.includes("mop")||t.includes("wash")},i.isEditorRoomCarpet=function(){let e=this.activeEditorRoom();if(!e)return!1;if(e.carpet===!0)return!0;let t=String(e.floorType??"").toLowerCase();return t==="carpet"||t.startsWith("carpet_")||t.startsWith("carpet-")},i.showWaterLevel=function(){if(this.isEditorRoomCarpet()||this.waterLevelOptions().length===0)return!1;let e=this.mopActive();if(e!==null)return e;let t=this.editorFields();return t?this.isMopMode(t.clean_mode):!1},i.mopActive=function(){let e=this.dashboardSnapshot?.()?.mop_active;return e==null?null:!!e},i.supportsRoomProfiles=function(){let e=this.dashboardSnapshot?.()?.supports_room_profiles;return e==null?!0:!!e},i.maxCleanPasses=function(){let e=Number(this.dashboardSnapshot?.()?.max_clean_passes);return Number.isFinite(e)&&e>=1?Math.min(Math.trunc(e),9):2},i.passesIsGlobal=function(){return!!this.dashboardSnapshot?.()?.passes_is_global},i.showEdgeMopping=function(){if(this.isEditorRoomCarpet())return!1;let e=this.editorFields();return e?this.isMopMode(e.clean_mode):!1},i._buildOptionListForRole=function(e,t){let r=this.adapterOptionsFor?.(e)??[];if(r.length===0)return[];let a=this._profileDerivedOptions(t),c=new Set,n=[];for(let s of r){let o=String(s?.value??"").trim();if(!o)continue;let l=o.toLowerCase();c.has(l)||(c.add(l),n.push({value:o,label:String(s?.label??o)}))}for(let s of a){let o=String(s??"").trim();if(!o)continue;let l=o.toLowerCase();c.has(l)||(c.add(l),n.push({value:o,label:o}))}return n},i.cleanModeOptions=function(){let e=this._buildOptionListForRole("clean_mode","clean_mode");return this.isEditorRoomCarpet()?e.filter(t=>!this.isMopMode(t.value)):e},i.suctionLevelOptions=function(){return this._buildOptionListForRole("fan_speed","fan_speed")},i.waterLevelOptions=function(){return this._buildOptionListForRole("water_level","water_level")},i.cleanIntensityOptions=function(){return this._buildOptionListForRole("clean_intensity","clean_intensity")},i.isCustomProfile=function(){let e=this.editorFields();return e?String(e.profile_name??"").toLowerCase()==="custom":!1},i.currentEditorManagedProfileName=function(){let e=this.editorFields();if(!e)return null;let t=String(e.profile_name??"").trim();return!t||t.toLowerCase()==="custom"?null:t}}var Je=new Set(["is_on","is_off","exists","missing"]),Oc=["is_on","is_off","exists","missing"],Lc=["equals","not_equals","in","not_in","exists","missing"],Pc=["equals","not_equals","gt","gte","lt","lte","exists","missing"],Nc=["equals","not_equals","in","not_in","exists","missing"],st=["is_on","is_off","exists","missing","equals","not_equals","gt","gte","lt","lte","in","not_in"];function Fc(){return{id:null,label:"",entity_id:"",kind:"blocker",operator:"is_on",value:null,enabled:!0,effect:{action:"exclude",reason:"",changes:{}},fan_out_room_ids:[]}}function Dc(i,e){let t=Array.isArray(i)?i.map(Number).filter(Number.isFinite):[],r=Number(e);if(!Number.isFinite(r))return t;let a=t.indexOf(r);return a>=0?t.splice(a,1):t.push(r),t.sort((c,n)=>c-n)}function je(i){if(i==null||i==="")return!1;if(typeof i=="number")return Number.isFinite(i);let e=String(i).trim();return e?Number.isFinite(Number(e)):!1}function ot(i){if(Array.isArray(i))return i.map(t=>String(t??"").trim()).filter(Boolean);let e=String(i??"").trim();return e?e.split(",").map(t=>t.trim()).filter(Boolean):[]}function Yr(i,e,t){if(Je.has(String(t??"")))return null;let r=e?.valueModeForOperator?.(t)??"text";if(r==="multi-select")return ot(i);if(r==="number"){if(i==null||i==="")return null;let a=Number(i);return Number.isFinite(a)?a:i}return i}function Ve(i,e){if(!i)return i;let t=e?.operators??st,r=t[0]??"equals",a=t.includes(i.operator)?i.operator:r,c=Yr(i.value,e,a);if(e?.category==="enum"){let n=new Set((e.options??[]).map(o=>String(o.value))),s=e.valueModeForOperator?.(a);s==="single-select"&&c!=null&&!n.has(String(c))&&(c=null),s==="multi-select"&&(c=ot(c).filter(o=>n.has(String(o))))}return{...i,operator:a,value:c}}function Hc(i){return Array.isArray(i)?i.join(", "):i}function zc(i,e,t){if(!t)return 0;let r=String(i??"").toLowerCase(),a=String(e??"").toLowerCase();return r===t?100:a===t?95:r.startsWith(t)?80:a.startsWith(t)?70:r.includes(t)?50:a.includes(t)?40:0}function Qr(i){i.roomRulesActiveRoomId=function(){return this._roomRulesActiveRoomId??null},i.setRoomRulesActiveRoom=function(e){let t=String(e??"").trim();this._roomRulesActiveRoomId=t||null,this._roomRulesDraft=null,this._roomRulesDraftMode=null,this._roomRulesSaveError=null},i.availableFanOutTargets=function(){let e=this.getRoomsForActiveMap?.()??[],t=this.resolvedRoomRulesRoom?.();return t?e.filter(r=>String(r.id)!==String(t.id)):e.slice()},i.resolvedRoomRulesRoom=function(){let e=this.getRoomsForActiveMap?.()??[];if(!e.length)return null;let t=this._roomRulesActiveRoomId;if(t){let r=e.find(a=>String(a.id)===String(t));if(r)return r}return e[0]},i.rulesForActiveRoomTab=function(){let e=this.resolvedRoomRulesRoom();return e?Array.isArray(e.rules)?e.rules:[]:[]},i.roomRulesDraft=function(){return this._roomRulesDraft??null},i.roomRulesDraftMode=function(){return this._roomRulesDraftMode??null},i.openNewRuleDraft=function(){this._roomRulesDraft=Ve(Fc(),this.ruleEntityDescriptor("")),this._roomRulesDraftMode="new",this._roomRulesSaveError=null},i.openEditRuleDraft=function(e){e&&(this._roomRulesDraft=Ve({id:e.id??null,label:e.label??"",entity_id:e.entity_id??"",kind:e.kind??"blocker",operator:e.operator??"is_on",value:e.value??null,enabled:e.enabled!==!1,effect:{action:e.effect?.action??(e.kind==="modifier"?"mutate":"exclude"),reason:e.effect?.reason??"",changes:{...e.effect?.changes??{}}},fan_out_room_ids:Array.isArray(e.fan_out_room_ids)?e.fan_out_room_ids.map(Number).filter(Number.isFinite):[]},this.ruleEntityDescriptor(e.entity_id??"")),this._roomRulesDraftMode="edit",this._roomRulesSaveError=null)},i.closeRulesDraft=function(){this._roomRulesDraft=null,this._roomRulesDraftMode=null,this._roomRulesSaveError=null},i.updateRuleDraftField=function(e,t){if(this._roomRulesDraft){if(e==="kind"){let r=t==="modifier"?"modifier":"blocker";this._roomRulesDraft=Ve({...this._roomRulesDraft,kind:r,effect:{...this._roomRulesDraft.effect,action:r==="modifier"?"mutate":"exclude",changes:r==="blocker"?{}:this._roomRulesDraft.effect.changes},fan_out_room_ids:r==="modifier"?this._roomRulesDraft.fan_out_room_ids??[]:[]},this.ruleEntityDescriptor(this._roomRulesDraft.entity_id))}else if(e==="operator")this._roomRulesDraft=Ve({...this._roomRulesDraft,operator:String(t??"is_on"),value:Je.has(String(t))?null:this._roomRulesDraft.value},this.ruleEntityDescriptor(this._roomRulesDraft.entity_id));else if(e==="enabled")this._roomRulesDraft={...this._roomRulesDraft,enabled:!!t};else if(e==="entity_id")this._roomRulesDraft=Ve({...this._roomRulesDraft,entity_id:String(t??"")},this.ruleEntityDescriptor(t));else if(e==="effect.reason")this._roomRulesDraft={...this._roomRulesDraft,effect:{...this._roomRulesDraft.effect,reason:String(t??"")}};else if(e.startsWith("effect.changes.")){let r=e.slice(15),a={...this._roomRulesDraft.effect.changes??{}};t==null?delete a[r]:a[r]=t,this._roomRulesDraft={...this._roomRulesDraft,effect:{...this._roomRulesDraft.effect,changes:a}}}else if(e==="fan_out_room_ids")this._roomRulesDraft={...this._roomRulesDraft,fan_out_room_ids:Dc(this._roomRulesDraft.fan_out_room_ids,t)};else{let r=this.ruleEntityDescriptor(this._roomRulesDraft.entity_id);this._roomRulesDraft={...this._roomRulesDraft,[e]:e==="value"?Yr(t,r,this._roomRulesDraft.operator):t}}this._roomRulesSaveError=null}},i.roomRulesDraftIsValid=function(){let e=this._roomRulesDraft;if(!e)return!1;let t=String(e.entity_id??"").trim();if(!t)return!1;let r=this.ruleEntityDescriptor(t);if(!r.entityExists||!(r.operators??[]).includes(e.operator))return!1;if(!Je.has(String(e.operator??""))){let a=r.valueModeForOperator?.(e.operator)??"text";if(a==="multi-select"){if(!ot(e.value).length)return!1}else if(a==="number"){if(!je(e.value))return!1}else if(!String(e.value??"").trim())return!1}if(e.kind==="modifier"){let a=e.effect?.changes??{};if(!Object.entries(a).filter(([n,s])=>s==null?!1:n==="clean_passes"?Number(s)===1||Number(s)===2:!0).length)return!1}return!0},i.roomRulesSaveError=function(){return this._roomRulesSaveError??null},i.setRoomRulesSaveError=function(e){this._roomRulesSaveError=e??null},i.ruleEntityDescriptor=function(e=null){let t=typeof e=="string"?e:e?.entity_id??this._roomRulesDraft?.entity_id??"",r=String(t??"").trim(),a=r?this.entity?.(r):null,c=a?.attributes??{},n=r.includes(".")?r.split(".")[0]:"",s=a?.state??null,o=Array.isArray(c.options)?c.options.map(u=>({value:String(u??""),label:String(u??"")})):[],l="unknown";["binary_sensor","switch","input_boolean"].includes(n)?l="boolean":["select","input_select"].includes(n)||o.length?l="enum":["number","input_number"].includes(n)?l="numeric":n==="sensor"?l=je(s)?"numeric":"text":String(s??"").toLowerCase()==="on"||String(s??"").toLowerCase()==="off"?l="boolean":r&&(l="text");let d=l==="boolean"?Oc:l==="enum"?Lc:l==="numeric"?Pc:l==="text"?Nc:st;return{entityId:r,entityExists:!!a,entityLabel:String((c.friendly_name??r)||"Entity"),currentState:s,category:l,operators:d,options:o,min:je(c.min)?Number(c.min):null,max:je(c.max)?Number(c.max):null,step:je(c.step)?Number(c.step):null,unit:c.unit_of_measurement??null,valueModeForOperator(u){return Je.has(String(u??""))||l==="boolean"?"none":l==="enum"?u==="in"||u==="not_in"?"multi-select":"single-select":l==="numeric"?"number":"text"}}},i.ruleOperatorGroups=function(e=null){let t=this.ruleEntityDescriptor(e),r=new Set(t.operators??st);return[{label:"State",operators:[{value:"is_on",label:"Is ON"},{value:"is_off",label:"Is OFF"}]},{label:"Existence",operators:[{value:"exists",label:"Exists"},{value:"missing",label:"Missing"}]},{label:"Equality",operators:[{value:"equals",label:"Equals"},{value:"not_equals",label:"Not equals"}]},{label:"Numeric",operators:[{value:"gt",label:">"},{value:"gte",label:"\u2265"},{value:"lt",label:"<"},{value:"lte",label:"\u2264"}]},{label:"List",operators:[{value:"in",label:"In list"},{value:"not_in",label:"Not in list"}]}].map(c=>({...c,operators:c.operators.filter(n=>r.has(n.value))})).filter(c=>c.operators.length>0)},i.ruleEntitySearchResults=function(e=null,t=12){let r=String(e??this._roomRulesDraft?.entity_id??"").trim().toLowerCase();return r.length<2?[]:Object.entries(this.hass?.states??{}).map(([c,n])=>{let s=String(n?.attributes?.friendly_name??"").trim(),o=zc(c,s,r);return o<=0?null:{entity_id:c,friendly_name:s,state:n?.state??null,domain:c.split(".")[0]??"",score:o}}).filter(Boolean).sort((c,n)=>n.score!==c.score?n.score-c.score:c.entity_id.localeCompare(n.entity_id)).slice(0,Math.max(1,Number(t)||12))},i.roomRulesForRoom=function(e){let r=(this.getRoomsForActiveMap?.()??[]).find(a=>String(a.id)===String(e));return r?Array.isArray(r.rules)?r.rules:[]:[]},i.ruleConditionSummary=function(e){let t=e.operator??"",r=Hc(e.value);switch(t){case"is_on":return"is ON";case"is_off":return"is OFF";case"exists":return"exists";case"missing":return"is missing";case"equals":return`= ${r??""}`;case"not_equals":return`!= ${r??""}`;case"gt":return`> ${r??""}`;case"gte":return`>= ${r??""}`;case"lt":return`< ${r??""}`;case"lte":return`<= ${r??""}`;case"in":return`in [${r??""}]`;case"not_in":return`not in [${r??""}]`;default:return t}},i.ruleEffectSummary=function(e){if(e.kind==="blocker"){let a=e.effect?.reason;return a?`Exclude - ${a}`:"Exclude room"}let t=e.effect?.changes??{},r=[];return t.clean_mode&&r.push(`mode: ${t.clean_mode}`),t.fan_speed&&r.push(`fan: ${t.fan_speed}`),t.water_level&&r.push(`water: ${t.water_level}`),t.clean_intensity&&r.push(`intensity: ${t.clean_intensity}`),t.clean_passes!=null&&r.push(`passes: ${t.clean_passes}`),t.edge_mopping!=null&&r.push(`edge mop: ${t.edge_mopping?"on":"off"}`),r.length?r.join(", "):"Modify settings"}}var lt={MAINTENANCE:"maintenance_items",REPLACEMENTS:"replacements"};function Xr(i){i._ensureMaintenanceState=function(){return this._maintenanceState||(this._maintenanceState={activeTab:lt.MAINTENANCE,modalItem:null,resetUi:{confirming:!1,pending:!1,success:"",error:""}}),this._maintenanceState},i.maintenanceActiveTab=function(){return this._ensureMaintenanceState().activeTab},i.setMaintenanceActiveTab=function(e){let t=this._ensureMaintenanceState(),r=String(e??"").trim().toLowerCase();r!==lt.MAINTENANCE&&r!==lt.REPLACEMENTS||(t.activeTab=r)},i.isMaintenanceTabActive=function(e){return this.maintenanceActiveTab()===String(e??"").trim().toLowerCase()},i.openMaintenanceModal=function(e){if(!e||typeof e!="object")return;let t=this._ensureMaintenanceState();t.modalItem={...e},t.resetUi={confirming:!1,pending:!1,success:"",error:""}},i.closeMaintenanceModal=function(){let e=this._ensureMaintenanceState();e.modalItem=null,e.resetUi={confirming:!1,pending:!1,success:"",error:""}},i.activeMaintenanceModalItem=function(){return this._ensureMaintenanceState().modalItem??null},i.isMaintenanceModalOpen=function(){return!!this.activeMaintenanceModalItem()},i.maintenanceResetUi=function(){return this._ensureMaintenanceState().resetUi},i.beginMaintenanceResetConfirmation=function(){let e=this.maintenanceResetUi();e.confirming=!0,e.error="",e.success=""},i.cancelMaintenanceResetConfirmation=function(){let e=this.maintenanceResetUi();e.confirming=!1,e.pending=!1,e.error=""},i.setMaintenanceResetPending=function(e){this.maintenanceResetUi().pending=!!e},i.setMaintenanceResetSuccess=function(e){let t=this.maintenanceResetUi();t.success=String(e??""),t.error="",t.pending=!1,t.confirming=!1},i.setMaintenanceResetError=function(e){let t=this.maintenanceResetUi();t.error=String(e??""),t.success="",t.pending=!1},i.canInvokeMaintenanceReset=function(e){return e?.can_reset===!0&&typeof e?.reset_service=="string"&&e.reset_service.length>0&&e?.reset_service_data!=null},i.findUpkeepItem=function(e,t,r=null){let a=this.dashboardUpkeep?.()??{},c=String(e??"").trim().toLowerCase(),n=String(t??"").trim().toLowerCase(),s=r==null?null:String(r).trim().toLowerCase();return[...Array.isArray(a.maintenance_items)?a.maintenance_items:[],...Array.isArray(a.replacement_items)?a.replacement_items:[]].find(l=>{let d=String(l?.kind??"").trim().toLowerCase(),u=String(l?.component??"").trim().toLowerCase(),m=l?.entity_id==null?null:String(l.entity_id).trim().toLowerCase();return!(d!==c||u!==n||s&&m&&m!==s)})??null}}var Bc=["App Shell & Typography","Cards & Surfaces","Borders & Shadows","Chips","Room Cards","Map","Floor Textures","Floor Textures \u2014 Tile","Floor Textures \u2014 Wood","Floor Textures \u2014 Marble","Floor Textures \u2014 Concrete","Floor Textures \u2014 Carpet Low","Floor Textures \u2014 Carpet High","Floor Textures \u2014 Granite","Queue & Ordering","Status, Confidence & Alerts","Learning & Metrics","Modals & Overlays"],jc=["Shared Foundations"];function dt(i){return[...Bc,...i||[],...jc]}var qs=dt(["Cat","Dog","Raccoon","Parrot","Snake"].map(i=>`Animal Companion \u2014 ${i}`));var Vc=Object.freeze(["color","text","shadow","size","number","duration","motion","typography","easing"]),qc=new Set(Vc),Ke=Object.freeze({unit:{min:0,max:1,step:.01},blur:{min:0,max:8,step:.5},angle:{min:-180,max:180,step:1},signed:{min:-1,max:1,step:.01}});function Gc(i){return String(i||"").replace(/^--evcc-/,"").replace(/-/g," ").replace(/\b\w/g,e=>e.toUpperCase()).trim()}function Uc(i,e="color"){return function(r,a=null,c=e,n=null){let s=qc.has(c)?c:e,o={key:r,label:a||Gc(r),group:i,type:s};return n&&typeof n=="object"&&(Number.isFinite(n.min)&&(o.min=n.min),Number.isFinite(n.max)&&(o.max=n.max),Number.isFinite(n.step)&&(o.step=n.step)),o}}function H(i,e="color"){let t=Uc(i,e);t.color=(a,c=null)=>t(a,c,"color"),t.text=(a,c=null)=>t(a,c,"text"),t.shadow=(a,c=null)=>t(a,c,"shadow"),t.size=(a,c=null)=>t(a,c,"size"),t.number=(a,c=null)=>t(a,c,"number"),t.duration=(a,c=null)=>t(a,c,"duration"),t.motion=(a,c=null)=>t(a,c,"motion"),t.typography=(a,c=null)=>t(a,c,"typography"),t.easing=(a,c=null)=>t(a,c,"easing");let r=a=>(c,n=null,s=null)=>t(c,n,"number",{...a,...s||{}});return t.unit=r(Ke.unit),t.blur=r(Ke.blur),t.angle=r(Ke.angle),t.signed=r(Ke.signed),t}var ke=H("App Shell & Typography","color"),K=H("Cards & Surfaces","color"),Ce=H("Borders & Shadows","color"),O=H("Chips","color"),ne=H("Room Cards","color"),oe=H("Map","color"),Us=H("Floor Textures","number"),$=H("Queue & Ordering","color"),L=H("Status, Confidence & Alerts","color"),A=H("Learning & Metrics","color"),C=H("Modals & Overlays","color"),te=H("Shared Foundations","size"),Ws=H("Animal Companion","color");var Zr=[ke.color("--evcc-accent","Accent"),ke.color("--evcc-accent-soft","Accent Soft"),ke.color("--evcc-text-muted","Text Muted"),ke.color("--evcc-text-on-accent","Text On Accent"),ke.color("--evcc-text-primary","Text Primary"),ke.color("--evcc-text-secondary","Text Secondary"),ke.color("--evcc-text-strong","Text Strong")];var ea=[K.color("--evcc-bg-input","BG Input"),K.color("--evcc-card-bg","Card BG"),K.size("--evcc-card-gap","Card Gap"),K.size("--evcc-card-min-height","Card Min Height"),K.size("--evcc-card-padding","Card Padding"),K.color("--evcc-panel-bg","Panel BG"),K.color("--evcc-surface-action","Surface Action"),K.color("--evcc-surface-action-hover","Surface Action Hover"),K.color("--evcc-surface-base","Surface Base"),K.color("--evcc-surface-card","Surface Card"),K.color("--evcc-surface-chip","Surface Chip"),K.color("--evcc-surface-input","Surface Input"),K.color("--evcc-surface-overlay","Surface Overlay"),K.color("--evcc-surface-panel","Surface Panel"),K.color("--evcc-surface-raised","Surface Raised"),K.color("--evcc-surface-subtle","Surface Subtle"),K.color("--evcc-surface-sunken","Surface Sunken"),K.color("--evcc-surface-warning","Surface Warning")];var ta=[Ce.color("--evcc-border-default","Border Default"),Ce.color("--evcc-border-strong","Border Strong"),Ce.color("--evcc-border-subtle","Border Subtle"),Ce.color("--evcc-border-warning","Border Warning"),Ce.shadow("--evcc-shadow-card","Shadow Card"),Ce.shadow("--evcc-shadow-hover","Shadow Hover")];var ra=[O.color("--evcc-chip-active-bg","Chip Active BG"),O.color("--evcc-chip-active-border","Chip Active Border"),O.color("--evcc-chip-active-text","Chip Active Text"),O.color("--evcc-chip-bg","Chip BG"),O.color("--evcc-chip-border","Chip Border"),O.color("--evcc-chip-excluded-bg","Chip Excluded BG"),O.color("--evcc-chip-excluded-border","Chip Excluded Border"),O.color("--evcc-chip-excluded-text","Chip Excluded Text"),O.size("--evcc-chip-font-size","Chip Font Size"),O.typography("--evcc-chip-font-weight","Chip Font Weight"),O.size("--evcc-chip-gap","Chip Gap"),O.size("--evcc-chip-height","Chip Height"),O.color("--evcc-chip-hover-bg","Chip Hover BG"),O.color("--evcc-chip-hover-border","Chip Hover Border"),O.color("--evcc-chip-hover-text","Chip Hover Text"),O.size("--evcc-chip-icon-height","Chip Icon Height"),O.size("--evcc-chip-icon-padding","Chip Icon Padding"),O.size("--evcc-chip-icon-size","Chip Icon Size"),O.color("--evcc-chip-included-bg","Chip Included BG"),O.color("--evcc-chip-included-border","Chip Included Border"),O.color("--evcc-chip-included-text","Chip Included Text"),O.color("--evcc-chip-neutral-bg","Chip Neutral BG"),O.size("--evcc-chip-padding","Chip Padding"),O.size("--evcc-chip-radius","Chip Radius"),O.color("--evcc-chip-success-bg","Chip Success BG"),O.color("--evcc-chip-success-border","Chip Success Border"),O.color("--evcc-chip-success-text","Chip Success Text"),O.color("--evcc-chip-text","Chip Text"),O.color("--evcc-chip-warning-bg","Chip Warning BG"),O.color("--evcc-chip-warning-border","Chip Warning Border"),O.color("--evcc-chip-warning-text","Chip Warning Text")];var aa=[ne.color("--evcc-profile-chip-bg","Profile Chip BG"),ne.color("--evcc-profile-chip-border","Profile Chip Border"),ne.color("--evcc-profile-chip-custom-bg","Profile Chip Custom BG"),ne.color("--evcc-profile-chip-custom-border","Profile Chip Custom Border"),ne.color("--evcc-profile-chip-custom-text","Profile Chip Custom Text"),ne.color("--evcc-profile-chip-text","Profile Chip Text"),ne.color("--evcc-room-chip-bg","Room Chip BG"),ne.color("--evcc-room-chip-border","Room Chip Border"),ne.color("--evcc-room-chip-text","Room Chip Text"),ne.number("--evcc-room-fill-opacity","Room Fill Opacity"),ne.size("--evcc-room-grid-columns","Room Grid Columns"),ne.size("--evcc-room-grid-gap","Room Grid Gap"),ne.size("--evcc-room-grid-min","Room Grid Min")];var ia=[oe.color("--evcc-map-label-bg","Map Label Background"),oe.color("--evcc-map-label-text","Map Label Text"),oe.color("--evcc-map-label-text-selected","Map Label Text (Selected)"),oe.color("--evcc-map-label-order-text","Map Order Badge Text"),oe.color("--evcc-map-tooltip-bg","Map Tooltip Background"),oe.color("--evcc-map-tooltip-border","Map Tooltip Border"),oe.color("--evcc-map-tooltip-text","Map Tooltip Text"),oe.color("--evcc-map-tooltip-hint","Map Tooltip Hint Text"),oe.color("--evcc-map-compose-selected-stroke","Composer Selected Outline"),oe.color("--evcc-map-compose-cut-fill","Composer Cutout Fill"),oe.color("--evcc-map-compose-cut-selected-fill","Composer Cutout Fill (Selected)"),oe.color("--evcc-map-vertex-selected-glow","Composer Selected Vertex Glow")];var Ye=H("Floor Textures","number"),Ie=H("Floor Textures \u2014 Tile","color"),Ne=H("Floor Textures \u2014 Wood","color"),re=H("Floor Textures \u2014 Marble","color"),qe=H("Floor Textures \u2014 Concrete","color"),ut=H("Floor Textures \u2014 Carpet Low","color"),mt=H("Floor Textures \u2014 Carpet High","color"),pt=H("Floor Textures \u2014 Granite","color"),ca=[Ye.unit("--evcc-floor-textures-card-enabled","Card Textures Enabled (0/1)",{step:1}),Ye.unit("--evcc-floor-textures-map-enabled","Map Textures Enabled (0/1)",{step:1}),Ye.unit("--evcc-floor-texture-opacity-card","Card Texture Opacity (all)"),Ye.unit("--evcc-floor-texture-opacity-map","Map Texture Opacity (all)"),Ie.color("--evcc-floor-tile-base","Tile Base Color"),Ie.color("--evcc-floor-tile-grout","Tile Grout Color"),Ie.color("--evcc-floor-tile-accent","Tile Grout Line Color"),Ie.unit("--evcc-floor-tile-opacity-card","Tile Card Opacity"),Ie.unit("--evcc-floor-tile-face-opacity","Tile Base Layer Opacity"),Ie.unit("--evcc-floor-tile-grout-opacity","Tile Grout Layer Opacity"),Ie.unit("--evcc-floor-tile-line-opacity","Tile Grout Line Layer Opacity"),Ne.color("--evcc-floor-wood-base","Wood Base Color"),Ne.color("--evcc-floor-wood-accent","Wood Seam Color"),Ne.unit("--evcc-floor-wood-opacity-card","Wood Card Opacity"),Ne.unit("--evcc-floor-wood-depth-opacity","Wood Depth Layer Opacity"),Ne.unit("--evcc-floor-wood-grain-opacity","Wood Grain Layer Opacity"),Ne.unit("--evcc-floor-wood-seam-opacity","Wood Seam Layer Opacity"),re.color("--evcc-floor-marble-base","Marble Base Color"),re.color("--evcc-floor-marble-micro","Marble Micro Color"),re.color("--evcc-floor-marble-accent","Marble Vein Color"),re.unit("--evcc-floor-marble-opacity-card","Marble Card Opacity"),re.unit("--evcc-floor-marble-base-opacity","Marble Base Layer Opacity"),re.unit("--evcc-floor-marble-micro-opacity","Marble Micro Layer Opacity"),re.unit("--evcc-floor-marble-vein-opacity","Marble Vein Opacity (master)"),re.blur("--evcc-floor-marble-vein-blur","Marble Vein Blur (master, px)"),re.signed("--evcc-floor-marble-vein-major-opacity","Marble Major Vein Opacity +/-"),re.signed("--evcc-floor-marble-vein-minor-opacity","Marble Minor Vein Opacity +/-"),re.signed("--evcc-floor-marble-vein-major-blur","Marble Major Vein Blur +/- (px)",{min:-8,max:8,step:.5}),re.signed("--evcc-floor-marble-vein-minor-blur","Marble Minor Vein Blur +/- (px)",{min:-8,max:8,step:.5}),re.signed("--evcc-floor-marble-vein-minor-light","Marble Minor Vein Lighten (L+)"),re.unit("--evcc-floor-marble-vein-minor-chroma","Marble Minor Vein Saturation (xC)",{max:2}),re.angle("--evcc-floor-marble-vein-minor-hue","Marble Minor Vein Hue Shift (deg)"),qe.color("--evcc-floor-concrete-base","Concrete Base Color"),qe.color("--evcc-floor-concrete-accent","Concrete Micro Color"),qe.unit("--evcc-floor-concrete-opacity-card","Concrete Card Opacity"),qe.unit("--evcc-floor-concrete-broad-opacity","Concrete Base Layer Opacity"),qe.unit("--evcc-floor-concrete-micro-opacity","Concrete Micro Layer Opacity"),ut.color("--evcc-floor-carpet-low-base","Carpet Low Base Color"),ut.unit("--evcc-floor-carpet-low-opacity-card","Carpet Low Card Opacity"),ut.unit("--evcc-floor-carpet-low-texture-opacity","Carpet Low Texture Layer Opacity"),mt.color("--evcc-floor-carpet-high-base","Carpet High Base Color"),mt.unit("--evcc-floor-carpet-high-opacity-card","Carpet High Card Opacity"),mt.unit("--evcc-floor-carpet-high-texture-opacity","Carpet High Texture Layer Opacity"),pt.color("--evcc-floor-granite-light-base","Granite Base Color"),pt.unit("--evcc-floor-granite-light-opacity-card","Granite Card Opacity"),pt.unit("--evcc-floor-granite-light-texture-opacity","Granite Texture Layer Opacity")];var na=[$.number("--evcc-drag-opacity","Drag Opacity"),$.number("--evcc-drag-scale","Drag Scale"),$.shadow("--evcc-drag-shadow","Drag Shadow"),$.color("--evcc-order-chip-bg","Order Chip BG"),$.color("--evcc-order-chip-border","Order Chip Border"),$.color("--evcc-order-chip-text","Order Chip Text"),$.color("--evcc-order-feedback-border","Order Feedback Border"),$.color("--evcc-order-target-outline","Order Target Outline"),$.text("--evcc-progress-complete","Progress Complete"),$.color("--evcc-progress-fill","Progress Fill"),$.color("--evcc-queue-chip-bg","Queue Chip BG"),$.color("--evcc-queue-chip-border","Queue Chip Border"),$.size("--evcc-queue-chip-gap","Queue Chip Gap"),$.color("--evcc-queue-chip-text","Queue Chip Text"),$.color("--evcc-queue-completed-bg","Queue Completed BG"),$.color("--evcc-queue-completed-border","Queue Completed Border"),$.number("--evcc-queue-completed-opacity","Queue Completed Opacity"),$.color("--evcc-queue-completed-text","Queue Completed Text"),$.color("--evcc-queue-current-bg","Queue Current BG"),$.color("--evcc-queue-current-border","Queue Current Border"),$.shadow("--evcc-queue-current-glow","Queue Current Glow"),$.color("--evcc-queue-current-text","Queue Current Text"),$.color("--evcc-queue-hover-bg","Queue Hover BG"),$.color("--evcc-queue-hover-border","Queue Hover Border"),$.color("--evcc-queue-hover-text","Queue Hover Text"),$.color("--evcc-queue-inferred-bg","Queue Inferred BG"),$.color("--evcc-queue-inferred-border","Queue Inferred Border"),$.shadow("--evcc-queue-inferred-glow","Queue Inferred Glow"),$.color("--evcc-queue-inferred-text","Queue Inferred Text"),$.color("--evcc-queue-order-bg","Queue Order BG"),$.color("--evcc-queue-order-border","Queue Order Border"),$.color("--evcc-queue-order-text","Queue Order Text"),$.color("--evcc-queue-pending-bg","Queue Pending BG"),$.color("--evcc-queue-pending-border","Queue Pending Border"),$.number("--evcc-queue-pending-opacity","Queue Pending Opacity"),$.color("--evcc-queue-pending-text","Queue Pending Text"),$.color("--evcc-queue-skipped-bg","Queue Skipped BG"),$.color("--evcc-queue-skipped-border","Queue Skipped Border"),$.color("--evcc-queue-skipped-text","Queue Skipped Text"),$.duration("--evcc-reorder-feedback-duration","Reorder Feedback Duration"),$.easing("--evcc-reorder-flip-easing","Reorder Flip Easing")];var sa=[L.color("--evcc-color-cleaning","Color Cleaning"),L.color("--evcc-color-docked","Color Docked"),L.color("--evcc-color-error","Color Error"),L.color("--evcc-color-idle","Color Idle"),L.color("--evcc-confidence-high-bg","Confidence High BG"),L.color("--evcc-confidence-high-border","Confidence High Border"),L.color("--evcc-confidence-high-text","Confidence High Text"),L.color("--evcc-confidence-low-bg","Confidence Low BG"),L.color("--evcc-confidence-low-border","Confidence Low Border"),L.color("--evcc-confidence-low-text","Confidence Low Text"),L.color("--evcc-confidence-medium-bg","Confidence Medium BG"),L.color("--evcc-confidence-medium-border","Confidence Medium Border"),L.color("--evcc-confidence-medium-text","Confidence Medium Text"),L.color("--evcc-sem-error","Sem Error"),L.color("--evcc-sem-info","Sem Info"),L.color("--evcc-sem-success","Sem Success"),L.color("--evcc-sem-warning","Sem Warning"),L.color("--evcc-status-cleaning-bg","Status Cleaning BG"),L.color("--evcc-status-cleaning-border","Status Cleaning Border"),L.color("--evcc-status-cleaning-text","Status Cleaning Text"),L.color("--evcc-status-dot-charging","Status Dot Charging"),L.color("--evcc-status-dot-cleaning","Status Dot Cleaning"),L.color("--evcc-status-dot-docked","Status Dot Docked"),L.color("--evcc-status-dot-error","Status Dot Error"),L.color("--evcc-status-dot-idle","Status Dot Idle"),L.color("--evcc-status-dot-offline","Status Dot Offline"),L.color("--evcc-status-dot-paused","Status Dot Paused"),L.color("--evcc-status-dot-returning","Status Dot Returning"),L.shadow("--evcc-status-dot-shadow","Status Dot Shadow"),L.color("--evcc-status-dot-unavailable","Status Dot Unavailable"),L.duration("--evcc-status-pulse-duration","Status Pulse Duration")];var oa=[A.color("--evcc-estimate-default-bg","Estimate Default BG"),A.color("--evcc-estimate-default-border","Estimate Default Border"),A.color("--evcc-estimate-default-text","Estimate Default Text"),A.color("--evcc-estimate-learned-bg","Estimate Learned BG"),A.color("--evcc-estimate-learned-border","Estimate Learned Border"),A.color("--evcc-estimate-learned-text","Estimate Learned Text"),A.duration("--evcc-learning-anim-duration-fast","Learning Anim Duration Fast"),A.duration("--evcc-learning-anim-duration-normal","Learning Anim Duration Normal"),A.duration("--evcc-learning-anim-duration-slow","Learning Anim Duration Slow"),A.text("--evcc-learning-anim-ease","Learning Anim Ease"),A.size("--evcc-learning-chip-font-size","Learning Chip Font Size"),A.typography("--evcc-learning-chip-font-weight","Learning Chip Font Weight"),A.size("--evcc-learning-chip-radius","Learning Chip Radius"),A.color("--evcc-learning-confidence-high-bg","Learning Confidence High BG"),A.color("--evcc-learning-confidence-high-border","Learning Confidence High Border"),A.text("--evcc-learning-confidence-high-gradient","Learning Confidence High Gradient"),A.color("--evcc-learning-confidence-high-text","Learning Confidence High Text"),A.color("--evcc-learning-confidence-low-border","Learning Confidence Low Border"),A.text("--evcc-learning-confidence-low-gradient","Learning Confidence Low Gradient"),A.color("--evcc-learning-confidence-low-text","Learning Confidence Low Text"),A.color("--evcc-learning-confidence-medium-bg","Learning Confidence Medium BG"),A.color("--evcc-learning-confidence-medium-border","Learning Confidence Medium Border"),A.text("--evcc-learning-confidence-medium-gradient","Learning Confidence Medium Gradient"),A.color("--evcc-learning-confidence-medium-text","Learning Confidence Medium Text"),A.color("--evcc-learning-confidence-neutral-border","Learning Confidence Neutral Border"),A.text("--evcc-learning-confidence-neutral-gradient","Learning Confidence Neutral Gradient"),A.color("--evcc-learning-confidence-neutral-text","Learning Confidence Neutral Text"),A.color("--evcc-learning-note-text","Learning Note Text"),A.color("--evcc-learning-panel-bg","Learning Panel BG"),A.color("--evcc-learning-panel-border","Learning Panel Border"),A.shadow("--evcc-learning-panel-shadow","Learning Panel Shadow"),A.color("--evcc-learning-reanchor-border","Learning Reanchor Border"),A.color("--evcc-learning-reanchor-highlight","Learning Reanchor Highlight"),A.color("--evcc-learning-text-muted","Learning Text Muted"),A.color("--evcc-learning-text-primary","Learning Text Primary"),A.color("--evcc-learning-text-secondary","Learning Text Secondary"),A.color("--evcc-learning-warning-text","Learning Warning Text")];var la=[C.color("--evcc-modal-accent","Modal Accent"),C.color("--evcc-modal-accent-bg","Modal Accent BG"),C.color("--evcc-modal-accent-border","Modal Accent Border"),C.color("--evcc-modal-accent-text","Modal Accent Text"),C.color("--evcc-modal-backdrop-bg","Modal Backdrop BG"),C.number("--evcc-modal-backdrop-blur","Modal Backdrop Blur"),C.color("--evcc-modal-bg","Modal BG"),C.color("--evcc-modal-border","Modal Border"),C.color("--evcc-modal-border-default","Modal Border Default"),C.color("--evcc-modal-border-strong","Modal Border Strong"),C.color("--evcc-modal-border-subtle","Modal Border Subtle"),C.color("--evcc-modal-chip-active-bg","Modal Chip Active BG"),C.color("--evcc-modal-chip-active-border","Modal Chip Active Border"),C.color("--evcc-modal-chip-active-text","Modal Chip Active Text"),C.color("--evcc-modal-chip-bg","Modal Chip BG"),C.color("--evcc-modal-chip-border","Modal Chip Border"),C.color("--evcc-modal-chip-hover-bg","Modal Chip Hover BG"),C.color("--evcc-modal-chip-hover-border","Modal Chip Hover Border"),C.color("--evcc-modal-chip-hover-text","Modal Chip Hover Text"),C.color("--evcc-modal-chip-text","Modal Chip Text"),C.color("--evcc-modal-footer-bg","Modal Footer BG"),C.color("--evcc-modal-header-bg","Modal Header BG"),C.color("--evcc-modal-input-bg","Modal Input BG"),C.size("--evcc-modal-padding","Modal Padding"),C.size("--evcc-modal-radius","Modal Radius"),C.size("--evcc-modal-section-gap","Modal Section Gap"),C.shadow("--evcc-modal-shadow","Modal Shadow"),C.color("--evcc-modal-surface-input","Modal Surface Input"),C.color("--evcc-modal-surface-panel","Modal Surface Panel"),C.color("--evcc-modal-surface-section","Modal Surface Section"),C.color("--evcc-modal-text-muted","Modal Text Muted"),C.color("--evcc-modal-text-primary","Modal Text Primary"),C.color("--evcc-modal-text-secondary","Modal Text Secondary"),C.color("--evcc-modal-warning-bg","Modal Warning BG"),C.color("--evcc-modal-warning-border","Modal Warning Border"),C.color("--evcc-modal-warning-text","Modal Warning Text")];var da=[te.typography("--evcc-font-family","Font Family"),te.size("--evcc-gap","Gap"),te.size("--evcc-grid-gap","Grid Gap"),te.motion("--evcc-hover-lift","Hover Lift"),te.size("--evcc-pad","Pad"),te.number("--evcc-press-scale","Press Scale"),te.size("--evcc-radius-card","Radius Card"),te.size("--evcc-radius-chip","Radius Chip"),te.size("--evcc-radius-inner","Radius Inner"),te.size("--evcc-radius-panel","Radius Panel"),te.size("--evcc-section-gap","Section Gap"),te.text("--evcc-space-lg","Space Lg"),te.text("--evcc-space-md","Space Md"),te.text("--evcc-space-sm","Space Sm"),te.motion("--evcc-transition-normal","Transition Normal")];var Fe="Animal Companion";function De(i){let e=String(i||"").replace(/[^a-z0-9-]/gi,""),t=e.charAt(0).toUpperCase()+e.slice(1);return`${Fe} \u2014 ${t}`}var se=H(Fe,"color"),Wc=[se.color("--evcc-animal-eye-good","Eye \u2014 Good (>50% battery)"),se.color("--evcc-animal-eye-mid","Eye \u2014 Mid (25\u201350%)"),se.color("--evcc-animal-eye-warn","Eye \u2014 Warn (15\u201325%)"),se.color("--evcc-animal-eye-low","Eye \u2014 Low (\u226415%)"),se.color("--evcc-animal-eye-charging","Eye \u2014 Charging (pulses)"),se.color("--evcc-animal-fur","Fur (all animals)"),se.color("--evcc-animal-fur-shadow","Fur Shadow (all)"),se.color("--evcc-animal-fur-highlight","Fur Highlight (all)"),se.color("--evcc-animal-eye","Eye Base (all)"),se.color("--evcc-animal-pupil","Pupil (all)"),se.color("--evcc-animal-nose","Nose (all)"),se.color("--evcc-animal-whisker","Whisker (all)"),se.color("--evcc-animal-ear-inner","Ear Inner (all)"),se.color("--evcc-animal-white-tip","White Tip / Accent (all)")],Jc=[{suffix:"eye-good",label:"Eye \u2014 Good"},{suffix:"eye-mid",label:"Eye \u2014 Mid"},{suffix:"eye-warn",label:"Eye \u2014 Warn"},{suffix:"eye-low",label:"Eye \u2014 Low"},{suffix:"eye-charging",label:"Eye \u2014 Charging"},{suffix:"fur",label:"Fur"},{suffix:"fur-shadow",label:"Fur Shadow"},{suffix:"fur-highlight",label:"Fur Highlight"},{suffix:"eye",label:"Eye Base"},{suffix:"pupil",label:"Pupil"},{suffix:"nose",label:"Nose"},{suffix:"whisker",label:"Whisker"},{suffix:"ear-inner",label:"Ear Inner"},{suffix:"white-tip",label:"White Tip / Accent"}];function Kc(i){let e=String(i||"").replace(/[^a-z0-9-]/gi,"");if(!e)return[];let t=De(e),r=H(t,"color");return Jc.map(({suffix:a,label:c})=>r.color(`--evcc-animal-${e}-${a}`,c))}function ua(i){let e=Array.isArray(i)?i.filter(Boolean):[];return{parent:Wc,perAnimal:e.map(t=>({group:De(t),tokens:Kc(t)}))}}function ma(i){let e=Array.isArray(i)?i.filter(Boolean):[];return[Fe,...e.map(De)]}var Yc=[Zr,ea,ta,ra,aa,ia,ca,na,sa,oa,la],Qc=[da],Xc=["cat","dog","raccoon","parrot","snake"];function Zc(){try{let i=typeof window<"u"&&window.AnimalSVG?.list?window.AnimalSVG.list():null;if(Array.isArray(i)&&i.length>0)return i}catch{}return Xc}function en(i){let e=new Set;for(let t of i){let r=String(t?.key??"");if(!r)throw new Error("[theme-tokens] Registry entry is missing key.");if(e.has(r))throw new Error(`[theme-tokens] Duplicate token key detected: ${r}`);e.add(r)}}var ue=[],ye={},tn={},ae=[];function pa(){let i=Zc(),{parent:e,perAnimal:t}=ua(i),r=t.flatMap(o=>o.tokens),c=[...Yc,e,r,...Qc].flat();en(c);let n=ma(i),s=dt(n);ue=c,ye=Object.freeze(Object.fromEntries(c.map(o=>[o.key,o]))),tn=Object.freeze(s.reduce((o,l)=>(o[l]=c.filter(d=>d.group===l),o),{})),ae=s}pa();typeof document<"u"&&document.addEventListener&&document.addEventListener("animal-svg-registered",()=>{try{pa()}catch(i){console.warn("[theme-tokens] rebuild on animal-svg-registered failed:",i)}});var rn={"--evcc-surface-base":"#1c2127","--evcc-accent":"#3b82f6","--evcc-text-primary":"#f0f2f5","--evcc-sem-success":"#4caf6e","--evcc-sem-warning":"#f5a623","--evcc-sem-error":"#e05252","--evcc-sem-info":"#5a90d6"};function He(i){if(typeof i!="string")return null;let e=i.trim(),t=e.match(/^#([0-9a-fA-F]{3,8})$/);if(t){let r=t[1];return(r.length===3||r.length===4)&&(r=r.slice(0,3).split("").map(a=>a+a).join("")),r.length>=6?{r:parseInt(r.slice(0,2),16),g:parseInt(r.slice(2,4),16),b:parseInt(r.slice(4,6),16)}:null}if(t=e.match(/^rgba?\(([^)]+)\)$/i),t){let r=t[1].split(",").map(a=>parseFloat(a));if(r.length>=3&&r.slice(0,3).every(a=>Number.isFinite(a)))return{r:r[0],g:r[1],b:r[2]}}return null}var vt=i=>(i/=255,i<=.03928?i/12.92:Math.pow((i+.055)/1.055,2.4)),Qe=({r:i,g:e,b:t})=>.2126*vt(i)+.7152*vt(e)+.0722*vt(t);function va(i,e){let t=Qe(i),r=Qe(e),a=Math.max(t,r),c=Math.min(t,r);return(a+.05)/(c+.05)}function ht({r:i,g:e,b:t}){i/=255,e/=255,t/=255;let r=Math.max(i,e,t),a=Math.min(i,e,t),c=r-a,n=(r+a)/2,s=c===0?0:c/(1-Math.abs(2*n-1)),o=0;return c!==0&&(r===i?o=((e-t)/c%6+6)%6:r===e?o=(t-i)/c+2:o=(i-e)/c+4,o*=60),[o,s,n]}function an(i){return i<15||i>=352?"red":i<40?"orange":i<66?"gold":i<160?"green":i<195?"teal":i<215?"cyan":i<255?"blue":i<290?"purple":"pink"}function cn(i){return i<66||i>=290?"warm":i>=160&&i<290?"cool":"neutral"}function nn({r:i,g:e,b:t},r){return r==="protan"?{r:.567*i+.433*e,g:.558*i+.442*e,b:.242*e+.758*t}:{r:.625*i+.375*e,g:.7*i+.3*e,b:.3*e+.7*t}}var sn=(i,e)=>Math.hypot(i.r-e.r,i.g-e.g,i.b-e.b);function on(i){let e=1/0;for(let t of["deutan","protan"]){let r=i.map(a=>nn(a,t));for(let a=0;a<r.length;a++)for(let c=a+1;c<r.length;c++)e=Math.min(e,sn(r[a],r[c]))}return e}var ha={lightLum:.5,monoSat:.15,highContrast:18,softContrast:13,cvdSafe:33,deepLum:.006,vividSat:.5,mutedSat:.2};function fa(i){let e=l=>He(i?.[l])||He(rn[l]),t=e("--evcc-surface-base"),r=e("--evcc-accent"),a=e("--evcc-text-primary"),c=["success","warning","error","info"].map(l=>e(`--evcc-sem-${l}`)),[n,s]=ht(r),[,o]=ht(t);return{baseLum:Qe(t),baseSat:o,accentHue:n,accentSat:s,textContrast:va(a,t),cvdMin:on(c)}}function ft(i,e={}){let t=fa(i),r=ha,a=new Set;return a.add(t.baseLum>r.lightLum?"light":"dark"),t.accentSat<r.monoSat?a.add("mono"):(a.add(an(t.accentHue)),a.add(cn(t.accentHue))),t.textContrast>=r.highContrast?a.add("high-contrast"):t.textContrast<r.softContrast&&a.add("soft"),t.baseLum<r.deepLum&&a.add("deep"),t.baseSat>=r.vividSat?a.add("vivid"):t.baseSat<r.mutedSat&&a.add("muted"),e.builtIn&&a.add("core"),[...a]}var ln={success:"#4caf6e",warning:"#f5a623",error:"#e05252",info:"#5a90d6"},ba=19,ga={deuteranopia:"red-green",protanopia:"red-green",tritanopia:"blue-yellow"},_a={deuteranopia:[[.367322,.860646,-.227968],[.280085,.672501,.047413],[-.01182,.04294,.968881]],protanopia:[[.152286,1.052583,-.204868],[.114503,.786281,.099216],[-.003882,-.048116,1.051998]],tritanopia:[[1.255528,-.076749,-.178779],[-.078411,.930809,.147602],[.004733,.691367,.3039]]},gt=i=>(i/=255,i<=.04045?i/12.92:Math.pow((i+.055)/1.055,2.4)),bt=i=>i<0?0:i>1?1:i;function dn({r:i,g:e,b:t},r){let a=gt(i),c=gt(e),n=gt(t),s=_a[r];return{r:bt(s[0][0]*a+s[0][1]*c+s[0][2]*n),g:bt(s[1][0]*a+s[1][1]*c+s[1][2]*n),b:bt(s[2][0]*a+s[2][1]*c+s[2][2]*n)}}function un({r:i,g:e,b:t}){let r=.4124*i+.3576*e+.1805*t,a=.2126*i+.7152*e+.0722*t,c=.0193*i+.1192*e+.9505*t,n=d=>d>.008856?Math.cbrt(d):7.787*d+16/116,s=n(r/.95047),o=n(a/1),l=n(c/1.08883);return{L:116*o-16,a:500*(s-o),b:200*(o-l)}}var mn=(i,e)=>Math.hypot(i.L-e.L,i.a-e.a,i.b-e.b);function _t(i,e={}){let t=e.threshold??ba,r=["success","warning","error","info"],a={};for(let d of r)a[d]=He(i?.[`--evcc-sem-${d}`])||He(ln[d]);let c=[],n={};for(let d of Object.keys(_a)){let u={};for(let v of r)u[v]=un(dn(a[v],d));let m=1/0,p=null;for(let v=0;v<r.length;v++)for(let f=v+1;f<r.length;f++){let h=mn(u[r[v]],u[r[f]]);h<m&&(m=h,p=[r[v],r[f]]),h<t&&c.push({pair:[r[v],r[f]],cvd:d,deltaE:+h.toFixed(1)})}n[d]={min:+m.toFixed(1),pair:p}}let s=null;for(let d of Object.keys(n)){let u={cvd:d,bucket:ga[d],pair:n[d].pair,deltaE:n[d].min};(!s||u.deltaE<s.deltaE)&&(s=u)}let o={};for(let d of Object.keys(n)){let u=ga[d];(!o[u]||n[d].min<o[u].min)&&(o[u]={min:n[d].min,pair:n[d].pair,cvd:d})}let l=null;for(let d of Object.keys(o))(l===null||o[d].min>o[l].min)&&(l=d);return{pass:c.length===0,minDeltaE:s?s.deltaE:1/0,weakest:s,buckets:o,bestBucket:l,perCvd:n,reasons:c}}var Ge=[{key:"mode",label:"Mode",tags:["dark","light"]},{key:"accent",label:"Accent",tags:["red","orange","gold","green","teal","cyan","blue","purple","pink","mono"]},{key:"temperature",label:"Temp",tags:["warm","cool","neutral"]},{key:"surface",label:"Surface",tags:["deep","vivid","muted"]},{key:"contrast",label:"Contrast",tags:["soft","high-contrast"]},{key:"a11y",label:"Access",tags:["colorblind-safe"]},{key:"cvd",label:"Best for",tags:["red-green","blue-yellow"]},{key:"source",label:"Source",tags:["core","community","generated","manual"]}],ya=(()=>{let i=new Map;for(let e of Ge)for(let t of e.tags)i.set(t,e.key);return i})(),Xe=i=>ya.get(i)||"vibe",yt=["aurora","cosmic","galaxy","nebula","ocean","sunset","forest","nature","winter","autumn","spring","summer","neon","retro","vaporwave","pastel","moody","cozy","minimal","vibrant","earthy","candy","dreamy","bold"];function xt(i){let e=[];for(let r of Ge)for(let a of r.tags)e.push(a);let t=r=>{let a=e.indexOf(r);return a===-1?e.length:a};return[...i].sort((r,a)=>t(r)-t(a)||r.localeCompare(a))}var pn=new Set(["dark","light","red","orange","gold","green","teal","cyan","blue","purple","pink","mono","warm","cool","neutral","deep","vivid","muted","soft","high-contrast","colorblind-safe","red-green","blue-yellow","core"]),xa=i=>String(i).toLowerCase().trim();function wa(i={}){let e={...i.tokens||{},...i.colors||{}},t=xa(i.source||""),r=ft(e,{builtIn:t==="core"}),a=(Array.isArray(i.tags)?i.tags:[]).map(xa).filter(Boolean),c=a.includes("colorblind-safe"),n=a.filter(l=>!pn.has(l)),s=_t(e),o=new Set([...r,...n]);return s.pass&&(o.add("colorblind-safe"),s.bestBucket&&o.add(s.bestBucket)),{tags:[...o],colorblind:{requested:c,verified:s.pass,minDeltaE:s.minDeltaE,weakest:s.weakest,buckets:s.buckets,bestBucket:s.bestBucket,perCvd:s.perCvd,reasons:s.reasons}}}function vn(i,e){let t=String(i||"").trim(),r;if(/^#[0-9a-fA-F]{8}$/.test(t))r=`#${t.slice(1,7)}`;else if(/^#[0-9a-fA-F]{6}$/.test(t))r=t;else return t;if(e==null)return t;let a=Math.max(0,Math.min(1,Number(e)));if(Number.isNaN(a))return t;let c=Math.round(a*255).toString(16).padStart(2,"0").toLowerCase();return`${r}${c}`}function Sa(i){i._emptyThemeDraft=function(){return{tokens:{},colors:{},alpha:{}}},i._themeDraftHasOverrides=function(e){return Object.keys(e.tokens).length>0||Object.keys(e.colors).length>0||Object.keys(e.alpha).length>0},i._applyThemeDraftBucket=function(e,t){!t||typeof t!="object"||Object.entries(t).forEach(([r,a])=>{if(a==null||a===""){delete e[r];return}e[r]=a})},i._normalizeThemeDraft=function(e){let t=this._emptyThemeDraft();return!e||typeof e!="object"||(this._applyThemeDraftBucket(t.tokens,e.tokens),this._applyThemeDraftBucket(t.colors,e.colors),this._applyThemeDraftBucket(t.alpha,e.alpha)),t},i.applyThemeDraftPatch=function(e){let t=this._ensureThemeState();this._applyThemeDraftBucket(t.workingDraft.tokens,e?.tokens),this._applyThemeDraftBucket(t.workingDraft.colors,e?.colors),this._applyThemeDraftBucket(t.workingDraft.alpha,e?.alpha),t.draftDirty=this._themeDraftHasOverrides(t.workingDraft)},i.applyThemeActivation=function(e,t={}){let r=this._ensureThemeState(),a=t.clearDraft!==!1;r.activeThemeId=e??null,a&&(r.workingDraft=this._emptyThemeDraft(),r.draftDirty=!1)},i._ensureThemeState=function(){return this._themeState||(this._themeState={library:{},librarySummary:[],defaultThemeId:null,activeThemeId:null,workingDraft:this._emptyThemeDraft(),draftDirty:!1,editorMode:"live",selectedThemeId:null,activeSubTab:"presets",focusedGroup:"",tokenSearchQuery:"",selectedGroupFilter:"all",groupOpen:{},groupSearchQueryByName:{},modifiedOnly:!1,presetFacets:{},presetSearchQuery:"",_presetTags:null,presetFiltersOpen:!1,presetTagEditId:null,themeJsonModal:{open:!1,mode:null,text:""},themeMode:"system",deviceThemeId:null},this._loadDeviceTheme()),this._themeState},i._deviceThemeKey=function(){return`evcc_theme_device_${this.config?.vacuum_entity_id??"default"}`},i._loadDeviceTheme=function(){let e=this._themeState;try{let t=localStorage.getItem(this._deviceThemeKey());if(!t)return;let r=JSON.parse(t);(r?.mode==="device"||r?.mode==="system")&&(e.themeMode=r.mode),typeof r?.themeId=="string"&&(e.deviceThemeId=r.themeId)}catch{}},i._persistDeviceTheme=function(){let e=this._ensureThemeState();try{localStorage.setItem(this._deviceThemeKey(),JSON.stringify({mode:e.themeMode,themeId:e.deviceThemeId}))}catch{}},i.getThemeMode=function(){return this._ensureThemeState().themeMode},i.isDeviceThemeMode=function(){return this._ensureThemeState().themeMode==="device"},i.getDeviceThemeId=function(){return this._ensureThemeState().deviceThemeId},i.effectiveActiveThemeId=function(){let e=this._ensureThemeState();if(e.themeMode==="device"&&e.deviceThemeId){if(e.library?.[e.deviceThemeId])return e.deviceThemeId;Object.keys(e.library||{}).length>0&&(e.deviceThemeId=null,this._persistDeviceTheme())}return e.activeThemeId},i.setThemeMode=function(e){let t=this._ensureThemeState();t.themeMode=e==="device"?"device":"system",t.themeMode==="device"&&!t.deviceThemeId&&(t.deviceThemeId=t.activeThemeId),this._persistDeviceTheme()},i.setDeviceThemeId=function(e){let t=this._ensureThemeState();t.deviceThemeId=e||null,this._persistDeviceTheme()},i.clearDeviceOverride=function(){let e=this._ensureThemeState();e.deviceThemeId=null,e.themeMode="system",this._persistDeviceTheme()},i.setBackendThemeState=function(e){let t=this._ensureThemeState();t.activeThemeId=e?.active_theme_id??null,t.workingDraft=this._normalizeThemeDraft(e?.working_draft),t.draftDirty=e?.draft_dirty??this._themeDraftHasOverrides(t.workingDraft),t.editorMode=e?.editor_mode??"live"},i.setThemeLibrary=function(e){let t=this._ensureThemeState();t.library=e?.library??{},t.librarySummary=e?.themes??[],t.defaultThemeId=e?.default_theme_id??null,t._presetTags=null},i.resolvedTheme=function(){let e=this._ensureThemeState(),t={},r={},a={},c={},n=e.library?.[this.effectiveActiveThemeId()]||null;return n&&(Object.entries(n.colors||{}).forEach(([s,o])=>{a[s]=o,r[s]="theme"}),Object.entries(n.alpha||{}).forEach(([s,o])=>{c[s]=o,r[s]||(r[s]="theme")}),Object.entries(n.tokens||{}).forEach(([s,o])=>{t[s]=o,r[s]="theme"})),Object.entries(e.workingDraft.colors).forEach(([s,o])=>{a[s]=o,r[s]="draft"}),Object.entries(e.workingDraft.alpha).forEach(([s,o])=>{c[s]=o,r[s]="draft"}),Object.entries(e.workingDraft.tokens).forEach(([s,o])=>{t[s]=o,r[s]="draft"}),Object.entries(a).forEach(([s,o])=>{let l=s in c?c[s]:null;t[s]=vn(o,l)}),{tokens:t,sources:r}},i.setThemeSubTab=function(e){this._ensureThemeState().activeSubTab=e},i.setThemeSearchQuery=function(e){this._ensureThemeState().tokenSearchQuery=String(e||"").toLowerCase()},i.setThemeModifiedOnly=function(e){this._ensureThemeState().modifiedOnly=!!e},i.setSelectedTheme=function(e){this._ensureThemeState().selectedThemeId=e},i.setThemeFocusedGroup=function(e){let t=this._ensureThemeState(),r=String(e||"").trim();t.focusedGroup=ae.includes(r)?r:""},i.getThemeFocusedGroup=function(){let e=String(this._ensureThemeState().focusedGroup||"").trim();return ae.includes(e)?e:""},i.currentThemePreviewGroup=function(){let e=this._ensureThemeState(),t=String(e.selectedGroupFilter||"").trim(),r=String(e.activeSubTab||"presets").trim().toLowerCase();if(ae.includes(t))return t;let a=this.getThemeFocusedGroup();if(ae.includes(a))return a;if(r==="palette")return"Shared Foundations";let c=ae.find(n=>this.isThemeGroupOpen(n));return c||"Shared Foundations"},i.setThemeGroupFilter=function(e){let t=this._ensureThemeState();t.selectedGroupFilter=String(e||"all")},i.toggleThemeGroup=function(e){let t=this._ensureThemeState();t.groupOpen[e]=!this.isThemeGroupOpen(e)},i.isThemeGroupOpen=function(e){let t=this._ensureThemeState();return e in t.groupOpen?!!t.groupOpen[e]:!0},i.setThemeGroupSearchQuery=function(e,t){let r=this._ensureThemeState();r.groupSearchQueryByName[e]=String(t||"").toLowerCase()},i.getThemeGroupSearchQuery=function(e){return this._ensureThemeState().groupSearchQueryByName[e]||""},i.getSelectedTheme=function(){let e=this._ensureThemeState();return e.library?.[e.selectedThemeId]||null},i.getActiveTheme=function(){return this._ensureThemeState().library?.[this.effectiveActiveThemeId()]||null},i.getThemeGroupFilter=function(){return this._ensureThemeState().selectedGroupFilter||"all"},i._presetTagsForLibrary=function(){let e=this._ensureThemeState();if(e._presetTags)return e._presetTags;let t={},r=e.library||{};return Object.keys(r).forEach(a=>{let c=r[a]||{},{tags:n}=wa(c),s=c.source?String(c.source).toLowerCase():"",o=s?[...new Set([...n,s])]:n;t[a]={tags:o,set:new Set(o)}}),e._presetTags=t,t},i.presetTagsFor=function(e){return(this._presetTagsForLibrary()[e]||{tags:[]}).tags},i.presentPresetTags=function(){let e=this._presetTagsForLibrary(),t=new Set;return Object.keys(e).forEach(r=>{e[r].tags.forEach(a=>t.add(a))}),t},i.togglePresetFacet=function(e,t){let r=this._ensureThemeState(),a=Array.isArray(r.presetFacets[e])?[...r.presetFacets[e]]:[],c=a.indexOf(t);c===-1?a.push(t):a.splice(c,1),a.length?r.presetFacets[e]=a:delete r.presetFacets[e]},i.isPresetFacetActive=function(e,t){let r=this._ensureThemeState().presetFacets[e];return Array.isArray(r)&&r.includes(t)},i.setPresetSearchQuery=function(e){this._ensureThemeState().presetSearchQuery=String(e||"").toLowerCase()},i.clearPresetFilters=function(){let e=this._ensureThemeState();e.presetFacets={},e.presetSearchQuery=""},i.hasActivePresetFilters=function(){let e=this._ensureThemeState();return Object.keys(e.presetFacets).length>0||!!e.presetSearchQuery},i.activePresetFacetCount=function(){let e=this._ensureThemeState().presetFacets;return Object.keys(e).reduce((t,r)=>t+(e[r]?.length||0),0)},i.getPresetFiltersOpen=function(){return!!this._ensureThemeState().presetFiltersOpen},i.togglePresetFilters=function(){let e=this._ensureThemeState();e.presetFiltersOpen=!e.presetFiltersOpen},i.openThemeExportModal=function(e){this._ensureThemeState().themeJsonModal={open:!0,mode:"export",text:String(e||"")}},i.openThemeImportModal=function(){this._ensureThemeState().themeJsonModal={open:!0,mode:"import",text:""}},i.closeThemeJsonModal=function(){this._ensureThemeState().themeJsonModal={open:!1,mode:null,text:""}},i.isThemeJsonModalOpen=function(){return!!this._ensureThemeState().themeJsonModal.open},i.themeJsonModalMode=function(){return this._ensureThemeState().themeJsonModal.mode},i.themeJsonModalText=function(){return this._ensureThemeState().themeJsonModal.text||""},i.getPresetTagEditId=function(){return this._ensureThemeState().presetTagEditId||null},i.setPresetTagEditId=function(e){this._ensureThemeState().presetTagEditId=e||null},i.presetVibeTags=function(e){let t=this._ensureThemeState().library?.[e]||{};return Array.isArray(t.tags)?t.tags.slice():[]},i.applyThemeTagsLocal=function(e,t){let r=this._ensureThemeState(),a=r.library?.[e];if(!a)return;let c=[],n=new Set;(Array.isArray(t)?t:[]).forEach(s=>{let o=String(s||"").trim().toLowerCase();o&&!n.has(o)&&(n.add(o),c.push(o))}),c.length?a.tags=c:delete a.tags,r._presetTags=null},i.filteredPresetIds=function(){let e=this._ensureThemeState(),t=e.library||{},r=this._presetTagsForLibrary(),a=e.presetFacets,c=Object.keys(a),n=e.presetSearchQuery;return Object.keys(t).filter(s=>{let o=r[s]||{tags:[],set:new Set};for(let l of c){let d=a[l];if(d.length&&!d.some(u=>o.set.has(u)))return!1}return!(n&&!(String(t[s]?.name||s).toLowerCase()+" "+o.tags.join(" ")).includes(n))})},i.tokenMatchesGlobalThemeSearch=function(e,t="",r=""){let a=String(r||"").toLowerCase();if(!a)return!0;let c=String(e?.label||"").toLowerCase(),n=String(e?.key||"").toLowerCase(),s=String(t||"").toLowerCase(),o=Array.isArray(e?.aliases)?e.aliases.map(u=>String(u||"").toLowerCase()):[],l=Array.isArray(e?.usage)?e.usage.map(u=>String(u||"").toLowerCase()):[],d=Array.isArray(e?.affects)?e.affects.map(u=>String(u||"").toLowerCase()):[];return!!(c.includes(a)||n.includes(a)||s.includes(a)||o.some(u=>u.includes(a))||l.some(u=>u.includes(a))||d.some(u=>u.includes(a)))},i.tokenMatchesThemeGroupSearch=function(e,t="",r){let a=this.getThemeGroupSearchQuery(r);return this.tokenMatchesGlobalThemeSearch(e,t,a)},i.filteredThemeTokens=function(e,t={}){let r=this._ensureThemeState(),{tokens:a,sources:c}=this.resolvedTheme(),n=r.tokenSearchQuery,s=r.modifiedOnly,o=r.selectedGroupFilter||"all",l=t.excludeKeys instanceof Set?t.excludeKeys:new Set;return e.filter(d=>{let u=d.key,m=a[u]||"",p=c[u]||"ha",v=d.group||"";if(l.has(u)||s&&p!=="draft")return!1;if(o==="modified"){if(p!=="draft")return!1}else if(o!=="all"&&v!==o&&!v.startsWith(o+" \u2014 "))return!1;return!!this.tokenMatchesGlobalThemeSearch(d,m,n)})},i.filteredThemeTokensForGroup=function(e,t,r={}){let{tokens:a}=this.resolvedTheme();return this.filteredThemeTokens(t,r).filter(c=>{if(c.group!==e)return!1;let n=a[c.key]||"";return this.tokenMatchesThemeGroupSearch(c,n,e)})},i.themeGroupCounts=function(e,t,r={}){let{sources:a}=this.resolvedTheme(),c=this.filteredThemeTokensForGroup(e,t,r),n=c.length;return{modified:c.filter(o=>(a[o.key]||"ha")==="draft").length,total:n}},i.shouldForceThemeGroupOpenForSearch=function(e,t,r={}){return this._ensureThemeState().tokenSearchQuery?this.themeGroupCounts(e,t,r).total>0:!1}}function Ra(i){i._mapViewActive=null,i._mapSegmentsData=null,i._selectedSegmentIds=null,i._mapViewStorageKey=function(){return`evcc_map_view_active_${Z(this.config?.vacuum??"")}`},i.isMapViewActive=function(){if(this._mapViewActive===null){let t=localStorage.getItem(this._mapViewStorageKey());this._mapViewActive=t==="true"}return this._mapViewActive},i.setMapViewActive=function(t){this._mapViewActive=!!t;try{localStorage.setItem(this._mapViewStorageKey(),String(this._mapViewActive))}catch{}},i.toggleMapView=function(){this.setMapViewActive(!this.isMapViewActive())},i.mapSegmentsData=function(){return this._mapSegmentsData},i.setMapSegmentsData=function(t){let r=this._mapSegmentsData?.map_id,a=`${r??""}:${this._mapSegmentsData?.active_custom_layout_id??""}`,c=`${t?.map_id??""}:${t?.active_custom_layout_id??""}`;this._mapSegmentsData=t,a!==c?(this._segmentRoomOverlay=null,this._dotAnchorOverlay=null,this._mapAnchorMode=!1,this._composeDraft=null,this._composeSelectedId=null,this._composeMergeFrom=null,this._composeLoadedFor=null,t?.map_id!==r&&this.resetMapTransform()):(this._segmentRoomOverlay=null,this._dotAnchorOverlay=null)},i.mapSegments=function(){return this._mapSegmentsData?.segments??[]},i.segmentationMode=function(){return this._mapSegmentsData?.segmentation_mode??"cv"},i.customLayouts=function(){return this._mapSegmentsData?.custom_layouts??[]},i.activeCustomLayoutId=function(){return this._mapSegmentsData?.active_custom_layout_id??null},i.activeCustomLayout=function(){let t=this.activeCustomLayoutId();return t==null?null:(this.customLayouts()||[]).find(r=>String(r.id)===String(t))??null},i._layoutEditor=null,i._ensureLayoutEditor=function(){return this._layoutEditor||(this._layoutEditor={open:!1,mode:"new",name:""}),this._layoutEditor},i.isLayoutEditorOpen=function(){return this._ensureLayoutEditor().open===!0},i.layoutEditorMode=function(){return this._ensureLayoutEditor().mode},i.layoutDraftName=function(){return this._ensureLayoutEditor().name},i.setLayoutDraftName=function(t){this._ensureLayoutEditor().name=String(t??"")},i.openNewLayoutEditor=function(){this._layoutEditor={open:!0,mode:"new",name:""}},i.openRenameLayoutEditor=function(){this._layoutEditor={open:!0,mode:"rename",name:this.activeCustomLayout()?.name??""}},i.closeLayoutEditor=function(){this._layoutEditor={open:!1,mode:"new",name:""}},i.mapImageUrl=function(){let t=this._mapSegmentsData?.image_variants??{};if(this.segmentationMode()==="custom"){let r=this.activeCustomLayout()?.backdrop_variant||"custom",a=t[r];return a?a.browser_url??null:r!=="custom"?null:(t.dark??t.default??t.light)?.browser_url??null}return(t.dark??t.default??t.light)?.browser_url??null},i._composeDraft=null,i._composeSelectedId=null,i._composeNextId=1,i.composeDraft=function(){return this._composeDraft===null&&(this._composeDraft=[]),this._composeDraft},i.composeSelectedId=function(){return this._composeSelectedId},i.selectComposeShape=function(t){this._composeSelectedId=t??null},i.addComposeShape=function(t){let r=new Set(this.composeDraft().map(s=>s.id)),a;do a=`draft_${this._composeNextId++}`;while(r.has(a));let c=this.composeDraft().length%6*5,n=t==="circle"?{id:a,type:"circle",cx:28+c,cy:28+c,r:14}:{id:a,type:"rect",x:22+c,y:22+c,w:28,h:22,angle:0};return this.composeDraft().push(n),this._composeSelectedId=a,n},i.updateComposeShape=function(t,r){let a=this.composeDraft().find(c=>c.id===t);a&&Object.assign(a,r)},i.deleteComposeShape=function(t){this._composeDraft=this.composeDraft().filter(r=>r.id!==t),this._composeSelectedId===t&&(this._composeSelectedId=null),this._composeMergeFrom===t&&(this._composeMergeFrom=null)},i.clearComposeDraft=function(){this._composeDraft=[],this._composeSelectedId=null,this._composeMergeFrom=null},i.moveComposeShape=function(t,r,a){let c=this.composeDraft().find(s=>s.id===t);if(!c)return;let n=(s,o,l)=>Math.max(o,Math.min(l,s));if(c.type==="circle")c.cx=n(c.cx+r,0,100),c.cy=n(c.cy+a,0,100);else if(c.type==="polygon"){let s=c.points.map(u=>u[0]),o=c.points.map(u=>u[1]),l=n(r,-Math.min(...s),100-Math.max(...s)),d=n(a,-Math.min(...o),100-Math.max(...o));c.points=c.points.map(([u,m])=>[u+l,m+d])}else c.x=n(c.x+r,0,100-c.w),c.y=n(c.y+a,0,100-c.h)},i.scaleComposeShape=function(t,r){let a=this.composeDraft().find(n=>n.id===t);if(!a)return;let c=(n,s,o)=>Math.max(s,Math.min(o,n));if(a.type==="circle")a.r=c(a.r*r,2,50);else if(a.type==="polygon"){let n=a.points.map(d=>d[0]),s=a.points.map(d=>d[1]),o=(Math.min(...n)+Math.max(...n))/2,l=(Math.min(...s)+Math.max(...s))/2;a.points=a.points.map(([d,u])=>[c(o+(d-o)*r,0,100),c(l+(u-l)*r,0,100)])}else{let n=a.x+a.w/2,s=a.y+a.h/2;a.w=c(a.w*r,3,100),a.h=c(a.h*r,3,100),a.x=c(n-a.w/2,0,100-a.w),a.y=c(s-a.h/2,0,100-a.h)}},i.resizeComposeShape=function(t,r,a){let c=this.composeDraft().find(l=>l.id===t);if(!c||c.type!=="rect")return;let n=(l,d,u)=>Math.max(d,Math.min(u,l)),s=c.x+c.w/2,o=c.y+c.h/2;r==="w"?(c.w=n(c.w+a,3,100),c.x=n(s-c.w/2,0,100-c.w)):(c.h=n(c.h+a,3,100),c.y=n(o-c.h/2,0,100-c.h))},i._composeStep=3,i.composeStep=function(){return this._composeStep},i.setComposeStep=function(t){this._composeStep=Number(t)||3},i.placeComposeShape=function(t,r,a){let c=this.composeDraft().find(s=>s.id===t);if(!c)return;let n=(s,o,l)=>Math.max(o,Math.min(l,s));if(c.type==="circle")c.cx=n(r,0,100),c.cy=n(a,0,100);else if(c.type==="polygon"){let s=c.points.map(u=>u[0]),o=c.points.map(u=>u[1]),l=(Math.min(...s)+Math.max(...s))/2,d=(Math.min(...o)+Math.max(...o))/2;this.moveComposeShape(t,r-l,a-d)}else c.x=n(r-c.w/2,0,100-c.w),c.y=n(a-c.h/2,0,100-c.h)},i.composeToSegments=function(){let t=a=>{let c=a.x+a.w/2,n=a.y+a.h/2,s=(a.angle||0)*Math.PI/180,o=Math.cos(s),l=Math.sin(s),d=(u,m)=>[Math.round((c+(u-c)*o-(m-n)*l)*100)/100,Math.round((n+(u-c)*l+(m-n)*o)*100)/100];return[d(a.x,a.y),d(a.x+a.w,a.y),d(a.x+a.w,a.y+a.h),d(a.x,a.y+a.h)]},r={};for(let a of this.composeDraft()){let c=a.group??a.id;(r[c]=r[c]||[]).push(a)}return Object.keys(r).map(a=>{let c=r[a],n=[...c].sort((o,l)=>(o.op==="subtract"?1:0)-(l.op==="subtract"?1:0)),s=c.find(o=>o.room_id!=null);return{id:a,room_id:s?s.room_id:void 0,primitives:n.map(o=>{let l=o.type==="circle"?{type:"circle",cx:o.cx,cy:o.cy,r:o.r}:o.type==="polygon"?{type:"polygon",points:o.points}:o.angle?{type:"polygon",points:t(o)}:{type:"rect",x:o.x,y:o.y,w:o.w,h:o.h};return o.op==="subtract"&&(l.op="subtract"),l})}})},i.loadComposeDraftFromSegments=function(t){let r=[];for(let c of t?.segments??[]){let n=c?.polygon_pct;!Array.isArray(n)||n.length<3||r.push({id:String(c.segment_id??`loaded_${r.length+1}`),type:"polygon",points:n.map(s=>[Number(s[0]),Number(s[1])]),room_id:c.room_id!=null?String(c.room_id):void 0})}this._composeDraft=r,this._composeSelectedId=null,this._composeMergeFrom=null,this._composeLoadedFor=this._composeKey(t);let a=0;for(let c of r){let n=/(\d+)$/.exec(c.id);n&&(a=Math.max(a,Number(n[1])))}this._composeNextId=a+1},i._composeKey=function(t){return`${t?.map_id??""}:${t?.active_custom_layout_id??""}`},i.maybeLoadComposeDraft=function(t){!t||(t.segmentation_mode??"cv")!=="custom"||this._composeLoadedFor!==this._composeKey(t)&&this.loadComposeDraftFromSegments(t)},i.assignComposeRoom=function(t,r){let a=this.composeDraft(),c=a.find(l=>l.id===t);if(!c)return;let n=r==null?void 0:String(r),s=c.room_id!=null&&String(c.room_id)===n?void 0:n,o=c.group??c.id;for(let l of a)(l.group??l.id)===o&&(l.room_id=s)},i._composeMergeFrom=null,i.composeMergeFrom=function(){return this._composeMergeFrom},i.startComposeMerge=function(t){this._composeMergeFrom=t??null},i.cancelComposeMerge=function(){this._composeMergeFrom=null},i.mergeComposeShapes=function(t,r){if(!t||!r||t===r)return;let a=this.composeDraft(),c=a.find(d=>d.id===t),n=a.find(d=>d.id===r);if(!c||!n)return;let s=c.group??c.id,o=n.group??n.id;for(let d of a)(d.group??d.id)===o&&(d.group=s);let l=c.room_id??n.room_id;for(let d of a)(d.group??d.id)===s&&(d.room_id=l)},i.splitComposeShape=function(t){let r=this.composeDraft().find(a=>a.id===t);r&&(r.group=void 0,r.op=void 0,r.room_id=void 0)},i.toggleComposeOp=function(t){let r=this.composeDraft().find(a=>a.id===t);r&&(r.op=r.op==="subtract"?void 0:"subtract")},i._composeMoveScope="room",i.composeMoveScope=function(){return this._composeMoveScope},i.setComposeMoveScope=function(t){this._composeMoveScope=t==="piece"?"piece":"room"},i._composeGroupMembers=function(t){let r=this.composeDraft(),a=r.find(n=>n.id===t);if(!a)return[];let c=a.group??a.id;return r.filter(n=>(n.group??n.id)===c)},i._composeIsMerged=function(t){return this._composeGroupMembers(t).length>=2},i._translateShape=function(t,r,a){t.type==="circle"?(t.cx+=r,t.cy+=a):t.type==="polygon"?t.points=t.points.map(([c,n])=>[c+r,n+a]):(t.x+=r,t.y+=a)},i._composeShapesBBox=function(t){let r=1/0,a=1/0,c=-1/0,n=-1/0,s=(o,l)=>{r=Math.min(r,o),c=Math.max(c,o),a=Math.min(a,l),n=Math.max(n,l)};for(let o of t)if(o.type==="circle")s(o.cx-o.r,o.cy-o.r),s(o.cx+o.r,o.cy+o.r);else if(o.type==="polygon")for(let[l,d]of o.points)s(l,d);else s(o.x,o.y),s(o.x+o.w,o.y+o.h);return{minX:r,minY:a,maxX:c,maxY:n}},i.moveComposeGroup=function(t,r,a){let c=this._composeGroupMembers(t);if(!c.length)return;let n=(d,u,m)=>Math.max(u,Math.min(m,d)),s=this._composeShapesBBox(c),o=n(r,-s.minX,100-s.maxX),l=n(a,-s.minY,100-s.maxY);for(let d of c)this._translateShape(d,o,l)},i.placeComposeGroup=function(t,r,a){let c=this._composeGroupMembers(t);if(!c.length)return;let n=this._composeShapesBBox(c);this.moveComposeGroup(t,r-(n.minX+n.maxX)/2,a-(n.minY+n.maxY)/2)},i.moveComposeScoped=function(t,r,a){this._composeMoveScope==="room"&&this._composeIsMerged(t)?this.moveComposeGroup(t,r,a):this.moveComposeShape(t,r,a)},i.placeComposeScoped=function(t,r,a){this._composeMoveScope==="room"&&this._composeIsMerged(t)?this.placeComposeGroup(t,r,a):this.placeComposeShape(t,r,a)},i.rotateComposeShape=function(t,r){let a=this.composeDraft().find(m=>m.id===t);if(!a||a.type==="circle")return;if(a.type==="rect"){a.angle=(((a.angle||0)+r)%360+360)%360;return}let c=a.points.map(m=>m[0]),n=a.points.map(m=>m[1]),s=(Math.min(...c)+Math.max(...c))/2,o=(Math.min(...n)+Math.max(...n))/2,l=r*Math.PI/180,d=Math.cos(l),u=Math.sin(l);a.points=a.points.map(([m,p])=>[Math.round((s+(m-s)*d-(p-o)*u)*100)/100,Math.round((o+(m-s)*u+(p-o)*d)*100)/100])},i._getSegmentIds=function(){return this._selectedSegmentIds||(this._selectedSegmentIds=new Set),this._selectedSegmentIds},i.selectedSegmentIds=function(){return this._getSegmentIds()},i.isSegmentSelected=function(t){return this._getSegmentIds().has(String(t))},i.toggleSegmentSelected=function(t){let r=this._getSegmentIds(),a=String(t);r.has(a)?r.delete(a):r.add(a)},i.clearSegmentSelection=function(){this._getSegmentIds().clear()},i.enableSegmentForRoom=function(t){let r=this.segmentIdForRoom(t);r&&this._getSegmentIds().add(String(r))},i.disableSegmentForRoom=function(t){let r=this.segmentIdForRoom(t);r&&this._getSegmentIds().delete(String(r))},i.selectedSegments=function(){let t=this.mapSegments(),r=[];for(let a of this._getSegmentIds()){let c=t.find(n=>String(n.segment_id)===a);c&&r.push(c)}return r},i._configSelectedSegmentId=null,i.configSelectedSegmentId=function(){return this._configSelectedSegmentId},i.setConfigSelectedSegmentId=function(t){this._configSelectedSegmentId=t!=null?String(t):null},i._segmentRoomOverlay=null,i._segRoomLegacyKey=function(){let t=this._mapSegmentsData?.map_id??"unknown";return`evcc_seg_rooms_${Z(this.config?.vacuum??"")}_${t}`},i._ensureSegmentRoomOverlay=function(){return this._segmentRoomOverlay||(this._segmentRoomOverlay=new Map),this._segmentRoomOverlay},i.getLegacySegmentRoomLinks=function(){try{let t=localStorage.getItem(this._segRoomLegacyKey());if(!t)return null;let r=JSON.parse(t);return!r||typeof r!="object"?null:r}catch{return null}},i.clearLegacySegmentRoomLinks=function(){try{localStorage.removeItem(this._segRoomLegacyKey())}catch{}},i.roomIdForSegment=function(t){let r=String(t),a=this.mapSegments().find(c=>String(c.segment_id)===r);return a?.room_id!=null?String(a.room_id):this._segmentRoomOverlay?.get(r)??null},i.segmentIdForRoom=function(t){let r=String(t),a=this.mapSegments().find(c=>c.room_id!=null&&String(c.room_id)===r);if(a)return String(a.segment_id);if(this._segmentRoomOverlay){for(let[c,n]of this._segmentRoomOverlay)if(n===r)return c}return null},i.assignSegmentRoom=function(t,r){let a=String(t),c=String(r),n=this._ensureSegmentRoomOverlay();for(let[s,o]of n)o===c&&s!==a&&n.delete(s);n.set(a,c)},i.unassignSegmentRoom=function(t){this._ensureSegmentRoomOverlay().delete(String(t))},i.configSelectedSegment=function(){let t=this._configSelectedSegmentId;return t?this.mapSegments().find(r=>String(r.segment_id)===t)??null:null},i._mapActionStatus=null,i.mapActionStatus=function(){return this._mapActionStatus},i.setMapActionStatus=function(t){this._mapActionStatus=t},i.clearMapActionStatus=function(){this._mapActionStatus=null};let e="map-config.delete-variant.";i.armMapVariantDelete=function(t){let r=t?String(t):null;r&&(this.disarmConfirmationsWithPrefix?.(e),this.armConfirmation?.(`${e}${r}`,{ttl:5e3,grace:0}))},i.clearMapVariantDeleteArm=function(){this.disarmConfirmationsWithPrefix?.(e)},i.mapVariantDeleteArmed=function(){let t=this.firstArmedConfirmationKey?.(e);return t?t.slice(e.length):null},i.isMapVariantDeleteArmed=function(t){return t?this.isConfirmationArmed?.(`${e}${String(t)}`)===!0:!1},i.mapNudgeStep=function(){let t=this._mapSegmentsData?.image_variants??{},r=t.dark??t.default??t.light,a=r?.width??1e3,c=r?.height??1e3;return{x:Math.max(1,Math.round(a*.005)),y:Math.max(1,Math.round(c*.005))}},i._mapZoom=1,i._mapTranslateX=0,i._mapTranslateY=0,i.mapZoom=function(){return this._mapZoom},i.mapTranslateX=function(){return this._mapTranslateX},i.mapTranslateY=function(){return this._mapTranslateY},i.resetMapTransform=function(){this._mapZoom=1,this._mapTranslateX=0,this._mapTranslateY=0},i.applyMapZoom=function(t,r,a){let c=Math.max(.5,Math.min(8,t)),n=c/this._mapZoom;this._mapTranslateX=r-(r-this._mapTranslateX)*n,this._mapTranslateY=a-(a-this._mapTranslateY)*n,this._mapZoom=c},i.applyMapPan=function(t,r){this._mapTranslateX+=t,this._mapTranslateY+=r},i._dotAnchorOverlay=null,i._mapAnchorMode=!1,i._dotAnchorLegacyKey=function(){let t=this._mapSegmentsData?.map_id??"unknown";return`evcc_dot_anchors_${Z(this.config?.vacuum??"")}_${t}`},i._ensureDotAnchorOverlay=function(){return this._dotAnchorOverlay||(this._dotAnchorOverlay=new Map),this._dotAnchorOverlay},i.getLegacyDotAnchors=function(){try{let t=localStorage.getItem(this._dotAnchorLegacyKey());if(!t)return null;let r=JSON.parse(t);return!r||typeof r!="object"?null:r}catch{return null}},i.clearLegacyDotAnchors=function(){try{localStorage.removeItem(this._dotAnchorLegacyKey())}catch{}},i.roomDotAnchor=function(t){let r=String(t);return this._dotAnchorOverlay?.has(r)?this._dotAnchorOverlay.get(r):this._mapSegmentsData?.companion_anchors?.[r]??null},i.setRoomDotAnchor=function(t,r,a){let c=String(t);this._ensureDotAnchorOverlay().set(c,{pct_x:r,pct_y:a})},i.isMapAnchorMode=function(){return this._mapAnchorMode},i.setMapAnchorMode=function(t){this._mapAnchorMode=!!t},i.currentMapRoom=function(){let t=this.rawRobotPosition?.();if(!t||t.x==null||t.y==null)return null;let r=this.getRoomsForActiveMap?.()??[],a=50;for(let c of r){if(c.is_transition||c.isTransition)continue;let n=c.bounds;if(n&&t.x>=n.min_x-a&&t.x<=n.max_x+a&&t.y>=n.min_y-a&&t.y<=n.max_y+a)return c}return null},i._configSelectedVertexIndex=null,i.configSelectedVertexIndex=function(){return this._configSelectedVertexIndex},i.setConfigSelectedVertexIndex=function(t){this._configSelectedVertexIndex=t!=null?Number(t):null},i._mapAnimalSelection=null,i._animalSelectionKey=function(){return`evcc_animal_${Z(this.config?.vacuum??"")}`},i.mapAnimalSelection=function(){if(this._mapAnimalSelection===null)try{this._mapAnimalSelection=localStorage.getItem(this._animalSelectionKey())??"cat"}catch{this._mapAnimalSelection="cat"}return this._mapAnimalSelection},i.setMapAnimalSelection=function(t){this._mapAnimalSelection=t;try{localStorage.setItem(this._animalSelectionKey(),t)}catch{}},i._mapAnimalScale=null,i._animalScaleKey=function(){return`evcc_animal_scale_${Z(this.config?.vacuum??"")}`},i.mapAnimalScale=function(){if(this._mapAnimalScale===null)try{let t=parseFloat(localStorage.getItem(this._animalScaleKey()));this._mapAnimalScale=isFinite(t)?t:1}catch{this._mapAnimalScale=1}return this._mapAnimalScale},i.setMapAnimalScale=function(t){let r=Math.max(.5,Math.min(3,Number(t)));this._mapAnimalScale=r;try{localStorage.setItem(this._animalScaleKey(),String(r))}catch{}},i._mapAnimalEnabled=null,i._animalEnabledKey=function(){return`evcc_animal_on_${Z(this.config?.vacuum??"")}`},i.mapAnimalEnabled=function(){if(this._mapAnimalEnabled===null)try{this._mapAnimalEnabled=localStorage.getItem(this._animalEnabledKey())!=="0"}catch{this._mapAnimalEnabled=!0}return this._mapAnimalEnabled},i.setMapAnimalEnabled=function(t){this._mapAnimalEnabled=!!t;try{localStorage.setItem(this._animalEnabledKey(),t?"1":"0")}catch{}},i.toggleMapAnimalEnabled=function(){this.setMapAnimalEnabled(!this.mapAnimalEnabled())},i._mapFloorTextureEnabled=null,i._roomFloorTextureEnabled=null,i._floorTexKey=function(t){return`evcc_floor_tex_${t}_${Z(this.config?.vacuum??"")}`},i._readFloorTex=function(t){try{let r=localStorage.getItem(this._floorTexKey(t));return r!==null?r!=="0":localStorage.getItem(`evcc_floor_tex_${Z(this.config?.vacuum??"")}`)!=="0"}catch{return!0}},i._writeFloorTex=function(t,r){try{localStorage.setItem(this._floorTexKey(t),r?"1":"0")}catch{}},i.mapFloorTextureEnabled=function(){return this._mapFloorTextureEnabled===null&&(this._mapFloorTextureEnabled=this._readFloorTex("map")),this._mapFloorTextureEnabled},i.setMapFloorTextureEnabled=function(t){this._mapFloorTextureEnabled=!!t,this._writeFloorTex("map",!!t)},i.toggleMapFloorTextureEnabled=function(){this.setMapFloorTextureEnabled(!this.mapFloorTextureEnabled())},i.roomFloorTextureEnabled=function(){return this._roomFloorTextureEnabled===null&&(this._roomFloorTextureEnabled=this._readFloorTex("rooms")),this._roomFloorTextureEnabled},i.setRoomFloorTextureEnabled=function(t){this._roomFloorTextureEnabled=!!t,this._writeFloorTex("rooms",!!t)},i.toggleRoomFloorTextureEnabled=function(){this.setRoomFloorTextureEnabled(!this.roomFloorTextureEnabled())}}function Ea(i){i._viewport="desktop",i.viewport=function(){return this._viewport},i.isMobileViewport=function(){return this._viewport==="mobile"},i.isCompactRender=function(){return this._viewport==="mobile"},i.setViewportFromWidth=function(e){let t=e<600?"mobile":"desktop";return t===this._viewport?!1:(this._viewport=t,!0)},i.setViewport=function(e){return e!=="mobile"&&e!=="desktop"||e===this._viewport?!1:(this._viewport=e,!0)}}var hn=0;function ka(i){i._ensureToastsState=function(){return this._toastsState||(this._toastsState={items:[]}),this._toastsState},i.pushToast=function(e,t={}){let r=this._ensureToastsState(),a=`toast-${++hn}`,c=["success","error","info"].includes(t.kind)?t.kind:"success",n=Number.isFinite(t.ttl)?Math.max(1e3,t.ttl):3500;return r.items.push({id:a,message:String(e??""),kind:c,expiresAt:Date.now()+n}),a},i.dismissToast=function(e){let t=this._ensureToastsState();t.items=t.items.filter(r=>r.id!==e)},i.activeToasts=function(){let e=this._ensureToastsState(),t=Date.now(),r=e.items.filter(a=>a.expiresAt>t);return r.length!==e.items.length&&(e.items=r),r}}function Ta(i){i._ensureConfirmationsState=function(){return this._confirmations||(this._confirmations={entries:new Map,renderTrigger:null}),this._confirmations},i.setConfirmationsRenderTrigger=function(e){this._ensureConfirmationsState().renderTrigger=typeof e=="function"?e:null},i.armConfirmation=function(e,t={}){if(!e)return;let r=this._ensureConfirmationsState(),a=Number.isFinite(t.ttl)?Math.max(0,t.ttl):5e3,c=Number.isFinite(t.grace)?Math.max(0,t.grace):700,n=r.entries.get(e);n?.timerId&&clearTimeout(n.timerId);let s=null;a>0&&(s=setTimeout(()=>{let o=r.entries.get(e);!o||o.timerId!==s||(r.entries.delete(e),r.renderTrigger?.())},a)),r.entries.set(e,{armedAt:Date.now(),ttl:a,grace:c,timerId:s})},i.disarmConfirmation=function(e){if(!e)return;let t=this._ensureConfirmationsState(),r=t.entries.get(e);r&&(r.timerId&&clearTimeout(r.timerId),t.entries.delete(e))},i.disarmAllConfirmations=function(){let e=this._ensureConfirmationsState();for(let t of e.entries.values())t.timerId&&clearTimeout(t.timerId);e.entries.clear()},i.disarmConfirmationsWithPrefix=function(e){if(!e)return;let t=this._ensureConfirmationsState();for(let r of[...t.entries.keys()])if(r.startsWith(e)){let a=t.entries.get(r);a?.timerId&&clearTimeout(a.timerId),t.entries.delete(r)}},i.firstArmedConfirmationKey=function(e){if(!e)return null;let t=this._ensureConfirmationsState();for(let r of t.entries.keys())if(r.startsWith(e))return r;return null},i.isConfirmationArmed=function(e){return e?this._ensureConfirmationsState().entries.has(e):!1},i.isConfirmationGuardActive=function(e){if(!e)return!1;let t=this._ensureConfirmationsState().entries.get(e);return t?Date.now()-t.armedAt<t.grace:!1}}function $a(i){i._ensureLearningState=function(){return this._learning||(this._learning={estimate:null,reanchored:null,completedRooms:[],nextRoom:null,jobActive:!1,summary:null,dashboardSnapshot:null,incompleteRunLog:null,troubleRoomsLog:null,roomEstimates:{},roomEstimateMeta:{stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}}),Array.isArray(this._learning.completedRooms)||(this._learning.completedRooms=[]),(!this._learning.roomEstimates||typeof this._learning.roomEstimates!="object")&&(this._learning.roomEstimates={}),(!this._learning.roomEstimateMeta||typeof this._learning.roomEstimateMeta!="object")&&(this._learning.roomEstimateMeta={stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}),this._learning},i.clearLearningState=function(){this._learning={estimate:null,reanchored:null,completedRooms:[],nextRoom:null,jobActive:!1,summary:null,dashboardSnapshot:null,incompleteRunLog:null,troubleRoomsLog:null,roomEstimates:{},roomEstimateMeta:{stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}}},i.clearLearningJobContext=function(){let e=this._ensureLearningState();e.estimate=null,e.reanchored=null,e.completedRooms=[],e.nextRoom=null,e.jobActive=!1,e.summary=null},i.learningState=function(){return this._ensureLearningState()},i.dashboardSnapshot=function(){return this._ensureLearningState().dashboardSnapshot??null},i.dashboardJobProgress=function(){return this.dashboardSnapshot()?.job_progress??null},i.dashboardJobControl=function(){return this.dashboardSnapshot()?.job_control??null},i.dashboardStartStatus=function(){return this.dashboardSnapshot()?.start_status??null},i.dashboardLifecycle=function(){return this.dashboardSnapshot()?.lifecycle??null},i.dashboardUpkeep=function(){return this.dashboardSnapshot()?.upkeep??null},i.supportsBaseStation=function(){let e=this.dashboardSnapshot()?.supports_base_station;return e==null?!0:!!e},i.supportsMapBounds=function(){let e=this.dashboardSnapshot()?.supports_map_bounds;return e==null?!0:!!e},i.dashboardAdapterVocabulary=function(){return this.dashboardSnapshot()?.adapter_vocabulary??null},i.adapterOptionsFor=function(e){let r=this.dashboardAdapterVocabulary()?.[`${e}_options`];return Array.isArray(r)?r:[]},i.adapterOptionValuesFor=function(e){return this.adapterOptionsFor(e).map(t=>t?.value).filter(Boolean)},i.dashboardStatusSummary=function(){return this.dashboardSnapshot()?.status_summary??null},i.dashboardAttentionSummary=function(){return this.dashboardSnapshot()?.attention_summary??null},i.dashboardPlannedJobEstimate=function(){return this.dashboardSnapshot()?.planned_job_estimate??null},i.dashboardPlannedWaterEstimate=function(){return this.dashboardPlannedJobEstimate()?.water_estimate??null},i.dashboardPlannedWaterRooms=function(){let e=this.dashboardPlannedWaterEstimate()?.rooms;return Array.isArray(e)?e:[]},i.dashboardPlannedWaterRoomForRoom=function(e,t=null){let r=e==null?null:String(e),a=t==null?null:String(t).trim().toLowerCase();return this.dashboardPlannedWaterRooms().find(c=>{let n=c?.room_id==null?null:String(c.room_id),s=c?.slug==null?null:String(c.slug).trim().toLowerCase();return!!(r!=null&&n===r||a&&s===a)})??null},i.dashboardPlannedJobEstimateAvailable=function(){return!!this.dashboardPlannedJobEstimate()?.available},i.dashboardPlannedJobEstimateTotalMinutes=function(){let e=Number(this.dashboardPlannedJobEstimate()?.total_minutes);return Number.isFinite(e)?e:null},i.dashboardJobProgressTimeline=function(){let e=this.dashboardJobProgress()?.timeline;return Array.isArray(e)?e:[]},i._dashboardJobIsActive=function(){let e=this.dashboardJobProgress();if(!e||typeof e!="object")return!1;if(typeof e.terminal=="boolean")return!e.terminal;let t=String(e.status??"").trim().toLowerCase();return t?!["complete","completed","finished","idle","terminal","not_started","inactive"].includes(t):!1},i.incompleteRunLog=function(){return this._ensureLearningState().incompleteRunLog??null},i.hasIncompleteRunLog=function(){let e=this.incompleteRunLog();if(!e)return!1;let t=e.missed_room_ids;return Array.isArray(t)&&t.length>0},i.incompleteRunMissedRoomIds=function(){let e=this.incompleteRunLog()?.missed_room_ids;return Array.isArray(e)?e:[]},i.incompleteRunMissedRooms=function(){let e=this.incompleteRunLog()?.missed_rooms;return Array.isArray(e)?e:[]},i.setIncompleteRunLog=function(e){let t=this._ensureLearningState();t.incompleteRunLog=e??null},i.clearIncompleteRunLog=function(){let e=this._ensureLearningState();e.incompleteRunLog=null},i.troubleRoomsLog=function(){return this._ensureLearningState().troubleRoomsLog??null},i.hasTroubleRooms=function(){let e=this.troubleRoomsLog();if(!e||typeof e!="object")return!1;let t=e.rooms;return!t||typeof t!="object"?!1:Object.values(t).some(r=>r?.is_trouble===!0)},i.troubleRoomForRoom=function(e){let t=this.troubleRoomsLog();if(!t||typeof t!="object")return null;let r=t.rooms;if(!r||typeof r!="object")return null;let a=String(e);return r[a]??null},i.setTroubleRoomsLog=function(e){let t=this._ensureLearningState();t.troubleRoomsLog=e??null},i.clearTroubleRoomsLog=function(){let e=this._ensureLearningState();e.troubleRoomsLog=null},i.learningEstimate=function(){return this._ensureLearningState().estimate??this.dashboardPlannedJobEstimate()??null},i.learningReanchored=function(){return this._ensureLearningState().reanchored??null},i.learningCompletedRooms=function(){return[...this._ensureLearningState().completedRooms]},i.learningNextRoom=function(){return this._ensureLearningState().nextRoom??null},i.learningJobActive=function(){return this._dashboardJobIsActive()?!0:!!this._ensureLearningState().jobActive},i.learningSummary=function(){return this._ensureLearningState().summary??null},i.hasLearningSummary=function(){return!!this._ensureLearningState().summary},i.clearLearningSummary=function(){let e=this._ensureLearningState();e.summary=null},i.roomEstimates=function(){return this._ensureLearningState().roomEstimates??{}},i.roomEstimateMeta=function(){return this._ensureLearningState().roomEstimateMeta??{}},i.hasRoomEstimates=function(){return Object.keys(this.roomEstimates()).length>0},i.roomEstimateForRoom=function(e){let t=String(e),r=this.roomEstimates();for(let[a,c]of Object.entries(r))if(String(a)===t)return c??null;return null},i.roomEstimatesStatsStale=function(){return!!this.roomEstimateMeta().stats_stale},i.roomEstimatesStatsRebuiltAt=function(){return this.roomEstimateMeta().stats_rebuilt_at??null},i.roomEstimatesEstimatedAt=function(){return this.roomEstimateMeta().estimated_at??null},i.roomEstimateCount=function(){let e=Number(this.roomEstimateMeta().room_count);return Number.isFinite(e)?e:Object.keys(this.roomEstimates()).length},i.setLearningEstimate=function(e){let t=this._ensureLearningState();t.estimate=e??null},i.setDashboardSnapshot=function(e){let t=this._ensureLearningState();t.dashboardSnapshot=e??null},i.setLearningReanchored=function(e){let t=this._ensureLearningState();t.reanchored=e??null},i.setLearningNextRoom=function(e){let t=this._ensureLearningState();t.nextRoom=e??null},i.setLearningJobActive=function(e){let t=this._ensureLearningState();t.jobActive=!!e},i.setLearningCompletedRooms=function(e){let t=this._ensureLearningState();t.completedRooms=Array.isArray(e)?[...e]:[]},i.setRoomEstimates=function(e){let t=this._ensureLearningState(),r={};for(let a of e?.rooms??[])a?.room_id!=null&&(r[a.room_id]=a);t.roomEstimates=r,t.roomEstimateMeta={stats_stale:!!e?.stats_stale,stats_rebuilt_at:e?.stats_rebuilt_at??null,estimated_at:e?.estimated_at??null,room_count:Number(e?.room_count??Object.keys(r).length)||0,current_battery:e?.current_battery??null,map_id:e?.map_id??null,vacuum_entity_id:e?.vacuum_entity_id??null}},i.clearRoomEstimates=function(){let e=this._ensureLearningState();e.roomEstimates={},e.roomEstimateMeta={stats_stale:!1,stats_rebuilt_at:null,estimated_at:null,room_count:0,current_battery:null,map_id:null,vacuum_entity_id:null}},i.pushCompletedLearningRoom=function(e){let t=this._ensureLearningState();if(!e||e.room_id==null)return;let r=Number(e.actual_duration_minutes);Number.isFinite(r)&&t.completedRooms.push({room_id:e.room_id,actual_duration_minutes:r})},i.beginLearningJob=function(){let e=this._ensureLearningState();e.jobActive=!0,e.reanchored=e.estimate??null,e.completedRooms=[],e.nextRoom=null,e.summary=null},i.endLearningJob=function(e=null){let t=this._ensureLearningState(),r=t.estimate,a=t.reanchored??r,c=Array.isArray(t.completedRooms)?t.completedRooms:[],n=Number(e?.actual_cleaning_minutes??e?.duration_minutes),s=Number(e?.room_count),o=Number(a?.total_minutes??r?.total_minutes??0);r||a||c.length||e?t.summary={finished_at:new Date().toISOString(),total_minutes:Number.isFinite(n)&&n>0?n:o||0,rooms_completed:Number.isFinite(s)&&s>0?s:c.length,predicted_total_minutes:o||null,battery_warning:!!a?.battery_warning,final_payload:a??r??null}:t.summary=null,t.jobActive=!1,t.reanchored=null,t.completedRooms=[],t.nextRoom=null},i.hasLearningEstimate=function(){let e=this.learningEstimate();return!!e&&!e?.error},i.learningEstimateError=function(){return this.learningEstimate()?.error??null},i.learningEstimateErrorDetail=function(){return this.learningEstimate()?.error_detail??null},i.learningStatsStale=function(){return!!this.learningEstimate()?.stats_stale},i.learningBatteryWarning=function(){return!!(this.dashboardJobProgress()??this.learningReanchored()??this.learningEstimate())?.battery_warning},i.learningCanRenderEstimatePanel=function(){let e=this.learningEstimate();return!(!e||e.error)},i.learningTotalMinutes=function(){let e=Number(this.dashboardPlannedJobEstimateTotalMinutes()??this.learningEstimate()?.total_minutes);return Number.isFinite(e)?e:null},i.learningJobEtaAt=function(){return this.dashboardJobProgress()?.status_summary?.eta_at??this.dashboardPlannedJobEstimate()?.job_eta_at??this.learningEstimate()?.job_eta_at??null},i.learningConfidenceBreakpoint=function(){return this.dashboardPlannedJobEstimate()?.confidence_breakpoint??this.learningEstimate()?.confidence_breakpoint??null},i.learningRoomTimeline=function(){let e=this.dashboardJobProgressTimeline();if(e.length)return e;let t=this.dashboardPlannedJobEstimate()?.room_timeline;if(Array.isArray(t)&&t.length)return t;let r=this.learningReanchored()??this.learningEstimate();return Array.isArray(r?.room_timeline)?r.room_timeline:[]},i.learningRoomsCompletedCount=function(){let e=this.dashboardJobProgress()?.completed_room_ids;if(Array.isArray(e))return e.length;let t=this.learningReanchored(),r=Number(t?.rooms_completed);return Number.isFinite(r)?r:this._ensureLearningState().completedRooms.length},i.learningRoomsRemainingCount=function(){let e=this.dashboardJobProgress()?.remaining_room_ids;if(Array.isArray(e))return e.length;let t=this.learningReanchored(),r=Number(t?.rooms_remaining);return Number.isFinite(r)?r:this.learningRoomTimeline().filter(c=>!c?.completed).length},i.learningAllCompleted=function(){let e=this.dashboardJobProgress();if(e&&typeof e.terminal=="boolean")return e.terminal;let t=this.learningReanchored();if(typeof t?.all_completed=="boolean")return t.all_completed;let r=this.learningNextRoom();return!!(r&&Object.keys(r).length===0)},i.learningLiveBannerRoom=function(){let e=this.dashboardJobProgress()?.current_room_id;if(e!=null){let r=this.learningTimelineEntryForRoom(e);if(r)return r}let t=this.learningRoomTimeline().find(r=>!!r?.current);return t||this.learningNextRoom()},i.learningTimelineEntryForRoom=function(e){let t=String(e);return this.learningRoomTimeline().find(r=>String(r?.room_id)===t)??null}}function Ma(i){i._ensureSetupState=function(){return this._setupState||(this._setupState={status:null,loading:!1,error:null,lastResult:null}),this._setupState},i.setupStatus=function(){return this._ensureSetupState().status??null},i.setSetupStatus=function(e){this._ensureSetupState().status=e??null},i.setupLoading=function(){return this._ensureSetupState().loading},i.setSetupLoading=function(e){this._ensureSetupState().loading=!!e},i.setupError=function(){return this._ensureSetupState().error??null},i.setSetupError=function(e){this._ensureSetupState().error=e??null},i.setupLastResult=function(){return this._ensureSetupState().lastResult??null},i.setSetupLastResult=function(e){this._ensureSetupState().lastResult=e??null},i._ensureSetupRoomEditor=function(){return this._setupRoomEditor||(this._setupRoomEditor={openMapId:null,rooms:null,loadingMapId:null,enabled:{},floorTypes:{},saving:!1,configuredMapIds:{}}),this._setupRoomEditor},i.setupRoomEditorOpenMapId=function(){return this._ensureSetupRoomEditor().openMapId??null},i.setupRoomEditorRooms=function(){return this._ensureSetupRoomEditor().rooms??null},i.setupRoomEditorLoadingMapId=function(){return this._ensureSetupRoomEditor().loadingMapId??null},i.setupRoomEditorSaving=function(){return this._ensureSetupRoomEditor().saving},i.isSetupMapConfigured=function(e){return!!this._ensureSetupRoomEditor().configuredMapIds[String(e)]},i.setSetupRoomEditorLoadingMapId=function(e){this._ensureSetupRoomEditor().loadingMapId=e??null},i.openSetupRoomEditor=function(e,t){let r=this._ensureSetupRoomEditor();r.openMapId=e,r.rooms=t,r.loadingMapId=null;let a={},c={};for(let n of t){let s=String(n.room_id);a[s]=!0,c[s]=n.floor_type||"hardwood"}r.enabled=a,r.floorTypes=c},i.closeSetupRoomEditor=function(){let e=this._ensureSetupRoomEditor();e.openMapId=null,e.rooms=null},i.toggleSetupRoom=function(e){let t=this._ensureSetupRoomEditor(),r=String(e);t.enabled[r]=t.enabled[r]===!1},i.setSetupRoomFloorType=function(e,t){this._ensureSetupRoomEditor().floorTypes[String(e)]=t},i.setSetupRoomEditorSaving=function(e){this._ensureSetupRoomEditor().saving=!!e},i.markSetupMapConfigured=function(e){this._ensureSetupRoomEditor().configuredMapIds[String(e)]=!0},i._ensureSetupDeleteState=function(){return this._setupDeleteState||(this._setupDeleteState={pendingMapId:null,stage:null,typedToken:"",deleting:!1}),this._setupDeleteState},i.setupDeletePendingMapId=function(){return this._ensureSetupDeleteState().pendingMapId??null},i.setupDeleteStage=function(){return this._ensureSetupDeleteState().stage??null},i.setupDeleteTypedToken=function(){return this._ensureSetupDeleteState().typedToken??""},i.setupDeleteDeleting=function(){return this._ensureSetupDeleteState().deleting},i.openSetupDeleteConfirm=function(e,t){let r=this._ensureSetupDeleteState();r.pendingMapId=e,r.stage=t?"typing":"confirm",r.typedToken="",r.deleting=!1},i.setSetupDeleteTypedToken=function(e){this._ensureSetupDeleteState().typedToken=e??""},i.setSetupDeleteDeleting=function(e){this._ensureSetupDeleteState().deleting=!!e},i.closeSetupDeleteConfirm=function(){let e=this._ensureSetupDeleteState();e.pendingMapId=null,e.stage=null,e.typedToken="",e.deleting=!1},i.setupRoomEditorEnabledIds=function(){let e=this._ensureSetupRoomEditor();return(e.rooms??[]).filter(r=>e.enabled[String(r.room_id)]!==!1).map(r=>r.room_id)},i.setupRoomEditorFloorTypesMap=function(){return{...this._ensureSetupRoomEditor().floorTypes}}}var ze={ALL:"all",HAS_BOUNDS:"has_bounds",NO_BOUNDS:"no_bounds"};function Aa(i){i._ensureMappingReviewState=function(){return this._mappingReviewState||(this._mappingReviewState={snapshot:null,filter:ze.ALL,pendingClearRoomId:null,pendingJobAction:null,pendingRebuildRoomId:null}),this._mappingReviewState},i.mappingBoundsSnapshot=function(){return this._ensureMappingReviewState().snapshot??null},i.setMappingBoundsSnapshot=function(e){this._ensureMappingReviewState().snapshot=e??null},i.mappingBoundsFilter=function(){return this._ensureMappingReviewState().filter},i.setMappingBoundsFilter=function(e){let t=this._ensureMappingReviewState();t.filter=Object.values(ze).includes(e)?e:ze.ALL},i.beginMappingBoundsClear=function(e){this._ensureMappingReviewState().pendingClearRoomId=String(e)},i.endMappingBoundsClear=function(){this._ensureMappingReviewState().pendingClearRoomId=null},i.isMappingBoundsClearPending=function(e){return this._ensureMappingReviewState().pendingClearRoomId===String(e)},i.beginMappingJobAction=function(e,t,r){this._ensureMappingReviewState().pendingJobAction={roomId:String(e),jobIndex:Number(t),action:r}},i.endMappingJobAction=function(){this._ensureMappingReviewState().pendingJobAction=null},i.isMappingJobActionPending=function(e,t){let r=this._ensureMappingReviewState().pendingJobAction;return r!==null&&r.roomId===String(e)&&r.jobIndex===Number(t)},i.beginMappingRebuild=function(e){this._ensureMappingReviewState().pendingRebuildRoomId=String(e)},i.endMappingRebuild=function(){this._ensureMappingReviewState().pendingRebuildRoomId=null},i.isMappingRebuildPending=function(e){return this._ensureMappingReviewState().pendingRebuildRoomId===String(e)},i.mappingBoundsFilterOptions=function(){return[{value:ze.ALL,label:"All Rooms"},{value:ze.HAS_BOUNDS,label:"Has Bounds"},{value:ze.NO_BOUNDS,label:"No Bounds"}]}}function Ca(i){i.reviewSubtab=function(){return this._reviewSubtab==="external"?"external":"history"},i.setReviewSubtab=function(e){this._reviewSubtab=e==="external"?"external":"history"},i.externalPendingRuns=function(){return Array.isArray(this._externalPending)?this._externalPending:[]},i.setExternalPendingRuns=function(e){this._externalPending=Array.isArray(e)?e:[]},i.externalBrand=function(){return typeof this._externalBrand=="string"&&this._externalBrand?this._externalBrand:null},i.setExternalBrand=function(e){this._externalBrand=typeof e=="string"&&e.trim()?e.trim():null},i.isExternalWizardOpen=function(){return this._extWizard!=null},i.externalWizard=function(){return this._extWizard||null},i.openExternalWizard=function(e){let t=Array.isArray(e?.segments)?e.segments:[],r={},a={};for(let c of t){let n=Number(c?.order??0);n>0&&(r[n]=!!c?.confident_boundary);let s=Array.isArray(c?.shortlist)&&c.shortlist[0]?c.shortlist[0]:null;a[n]={room_id:s?s.room_id:null,edge_mopping:!1,override:!1,overrides:{}}}this._extWizard={pendingJobId:e?.pending_job_id||null,mapId:e?.map_id||null,segments:t,splits:r,assignments:a,rooms:Array.isArray(e?.rooms)?e.rooms:[],candidates:Array.isArray(e?.candidates)?e.candidates:[],activeBoundaries:Array.isArray(e?.active_boundaries)?e.active_boundaries.map(Number):[],resegmentable:!!e?.resegmentable,suggestedRoomCount:Number(e?.suggested_room_count??t.length)||t.length,resegmentMeta:null,step:1,blocked:null,busy:!1,error:null}},i.applyResegmentResult=function(e){let t=this._extWizard;if(!t||!e)return;let r=Array.isArray(e.segments)?e.segments:[],a={};for(let c of r){let n=Number(c?.order??0),s=Array.isArray(c?.shortlist)&&c.shortlist[0]?c.shortlist[0]:null;a[n]={room_id:s?s.room_id:null,edge_mopping:!1,override:!1,overrides:{}}}t.segments=r,t.assignments=a,Array.isArray(e.candidates)&&(t.candidates=e.candidates),t.activeBoundaries=Array.isArray(e.active_boundaries)?e.active_boundaries.map(Number):[],e.suggested_room_count!=null&&(t.suggestedRoomCount=Number(e.suggested_room_count)),t.resegmentMeta=e.capped||e.message?{capped:!!e.capped,capped_at:e.capped_at,message:e.message||null}:null},i.closeExternalWizard=function(){this._extWizard=null},i.setExternalWizardStep=function(e){this._extWizard&&(this._extWizard.step=Number(e)||1)},i.toggleExternalSplit=function(e){let t=this._extWizard;t&&Object.prototype.hasOwnProperty.call(t.splits,e)&&(t.splits[e]=!t.splits[e])},i.setExternalAssignment=function(e,t){let r=this._extWizard;if(!r)return;let a=r.assignments[e]||{overrides:{}};r.assignments[e]={...a,...t}},i.setExternalAssignmentOverride=function(e,t,r){let a=this._extWizard;if(!a)return;let c=a.assignments[e]||{overrides:{}},n={...c.overrides||{},[t]:r};a.assignments[e]={...c,overrides:n}},i.setExternalWizardBlocked=function(e){this._extWizard&&(this._extWizard.blocked=Array.isArray(e)?e:null)},i.setExternalWizardBusy=function(e){this._extWizard&&(this._extWizard.busy=!!e)},i.setExternalWizardError=function(e){this._extWizard&&(this._extWizard.error=e||null)},i.externalWizardGroups=function(){let e=this._extWizard;if(!e)return[];if(e.resegmentable)return(e.segments||[]).map(r=>({orders:[Number(r?.order??0)],lead:r,segments:[r]}));let t=[];for(let r of e.segments){let a=Number(r?.order??0);if(a===0||e.splits[a]||t.length===0)t.push({orders:[a],lead:r,segments:[r]});else{let n=t[t.length-1];n.orders.push(a),n.segments.push(r)}}return t}}var N=class{constructor(e,t){this.hass=e,this.config=t}sync(e,t){return this.hass=e,this.config=t,this}};Nr(N.prototype);Ta(N.prototype);Fr(N.prototype);Dr(N.prototype);Hr(N.prototype);zr(N.prototype);Br(N.prototype);qr(N.prototype);Gr(N.prototype);Ur(N.prototype);Wr(N.prototype);Jr(N.prototype);Kr(N.prototype);Qr(N.prototype);Xr(N.prototype);Sa(N.prototype);Ra(N.prototype);Ea(N.prototype);ka(N.prototype);$a(N.prototype);Ma(N.prototype);Aa(N.prototype);Ca(N.prototype);function Ia(i){i.escapeHtml=function(e){return String(e??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")},i.formatRelativeAgo=function(e){if(e==null||e==="")return null;let t=Date.parse(String(e));if(!Number.isFinite(t))return null;let r=Date.now()-t;if(r<0)return null;let a=r/6e4;if(a<1)return"just now";if(a<60)return`${Math.round(a)}m ago`;let c=a/60;if(c<24)return`${Math.round(c)}h ago`;let n=c/24;return n<1.5?"yesterday":n<7?`${Math.round(n)}d ago`:n<30?`${Math.round(n/7)}w ago`:n<365?`${Math.round(n/30)}mo ago`:`${Math.round(n/365)}y ago`},i.renderSelect=function(e,t,r,a,c=!1){let n=Array.isArray(r)?r:[];return`
      <label class="evcc-field">
        <span class="evcc-field-label">${this.escapeHtml(e)}</span>
        <select class="${this.escapeHtml(t)}" ${c?"disabled":""}>
          ${n.map(s=>{let o=typeof s=="object"?s.value:s,l=typeof s=="object"?s.label:s,d=String(o)===String(a)?"selected":"";return`<option value="${this.escapeHtml(String(o??""))}" ${d}>
                      ${this.escapeHtml(String(l??""))}
                    </option>`}).join("")}
        </select>
      </label>
    `},i.renderChipSelect=function(e,t,r,a,c=!1){let n=Array.isArray(r)?r:[];return`
      <div class="evcc-chip-select ${this.escapeHtml(t)}">
        ${e?`<div class="evcc-field-label">${this.escapeHtml(e)}</div>`:""}
        <div class="evcc-chips" role="listbox">
          ${n.map(s=>{let o=typeof s=="object"?s.value:s,l=typeof s=="object"?s.label:s;return`<button
                      type="button"
                      class="evcc-chip ${String(o)===String(a)?"active":""}"
                      data-value="${this.escapeHtml(String(o??""))}"
                      ${c?"disabled":""}
                    >${this.escapeHtml(String(l??""))}</button>`}).join("")}
        </div>
      </div>
    `},i.renderStatusBadge=function(e,t=""){return`
      <span class="evcc-status-badge ${this.escapeHtml(t)}">
        ${this.escapeHtml(e)}
      </span>
    `},i.formatTimestamp=function(e,t={},r=""){if(!e)return r;let a=new Date(e);return Number.isNaN(a.getTime())?r:a.toLocaleString([],t)}}function Oa(i){i.renderBaseStationView=function(e){let{state:t}=e,r=t.dashboardUpkeep?.()??{},a=t.dockStatusLabel?.()??t.dockStatus?.()??r.dock_status_label??r.dock_status??null,c=t.dockLifecycleStateLabel?.()??t.dockLifecycleState?.()??null,n=t.dockTaskStatusLabel?.()??t.dockTaskStatus?.()??null,s=t.isDocked?.()??!1,o=t.dockActionStatus?.()??null,l=t.dashboardPlannedWaterEstimate?.()??null,d=r.dock_events??{},u=t.pauseTimeoutMinutesDefault?.(),p=[{id:"wash_mop",label:"Wash Mop"},{id:"dry_mop",label:"Dry Mop"},{id:"stop_dry_mop",label:"Stop Drying"},{id:"empty_dust",label:"Empty Dust"}].filter(({id:b})=>t.dockActionGate?.(b)?.supported!==!1),v=p.map(({id:b,label:w})=>this._renderDockActionCard(b,w,t)).join(""),f=t.dockActionGate?.("wash_mop")?.supported!==!1,h=p.length>0;return`
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
              ${this._renderBaseStationStat("Lifecycle",c||"Unknown")}
              ${this._renderBaseStationStat("Task",n||"Unknown")}
              ${this._renderBaseStationStat("Docked",s?"Yes":"No")}
            </div>

            ${r.updated_at||o?.updated_at?`
              <div class="evcc-base-station-updated">
                Updated ${this.escapeHtml(this._formatBaseStationTimestamp(o?.updated_at??r.updated_at))}
              </div>
            `:""}
          </section>

          ${f?`
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
          `:""}

          ${h?`
            <section class="evcc-base-station-panel evcc-base-station-panel--wide">
              <div class="evcc-base-station-panel-header">
                <div>
                  <div class="evcc-base-station-panel-title">Recent Dock Activity</div>
                  <div class="evcc-base-station-panel-subtitle">
                    Last known dock service activity
                  </div>
                </div>
              </div>

              <div class="evcc-base-station-activity-grid">
                ${t.dockActionGate?.("wash_mop")?.supported!==!1?this._renderBaseStationActivityCard("Mop Wash",d.last_mop_wash,d.mop_wash_count):""}
                ${t.dockActionGate?.("empty_dust")?.supported!==!1?this._renderBaseStationActivityCard("Dust Empty",d.last_dust_empty,d.dust_empty_count):""}
                ${t.dockActionGate?.("dry_mop")?.supported!==!1?this._renderBaseStationActivityCard("Dry Start",d.last_dry_start,d.dry_start_count,d.last_dry_duration):""}
              </div>
            </section>
          `:""}

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
              ${[15,30,45,60].map(b=>`
                <button
                  type="button"
                  class="evcc-chip ${u===b?"active":""}"
                  data-pause-timeout-minutes="${b}"
                >${b} min</button>
              `).join("")}
            </div>
          </section>

          ${p.length>0?`
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
          `:""}

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
    `},i._renderDockActionCard=function(e,t,r){let a=r.dockActionGate?.(e)??{},c=a?.allowed===!0,n=r.isDockActionPending?.(e)??!1,s=a?.reason_label??"",o=a?.message??"";return`
      <button
        type="button"
        class="evcc-base-station-action-card ${c?"evcc-base-station-action-card--allowed":"evcc-base-station-action-card--blocked"}"
        data-dock-action="${this.escapeHtml(e)}"
        ${c&&!n?"":"disabled"}
        title="${this.escapeHtml(o||s||(c?t:"Action unavailable"))}"
      >
        <div class="evcc-base-station-action-title">${this.escapeHtml(t)}</div>
        <div class="evcc-base-station-action-state">
          ${this.escapeHtml(n?"Running...":c?"Ready":"Unavailable")}
        </div>
        <div class="evcc-base-station-action-detail">
          ${this.escapeHtml(o||s||"Action available")}
        </div>
      </button>
    `},i._formatBaseStationLabel=function(e){let t=String(e??"").trim();return t?t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Unknown"},i._formatBaseStationTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatBaseStationMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"Unknown"},i._formatBaseStationProjectedTank=function(e){let t=Number(e?.estimated_clean_tank_remaining_ml),r=Number(e?.estimated_clean_tank_remaining_percent);return Number.isFinite(t)?Number.isFinite(r)?`${Math.round(t)} ml (${Math.round(r)}%)`:`${Math.round(t)} ml`:"Unknown"},i._formatBaseStationWaterLevel=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)}%`:this._formatBaseStationLabel(e)},i._formatBaseStationDuration=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:String(e??"")}}function La(i){i.renderMetricsView=function(e){let{state:t}=e,r=t.metricsSnapshot?.();if(!r)return'<div class="evcc-empty">Loading metrics...</div>';if(r.available===!1)return`
        <div class="evcc-metrics-view">
          <div class="evcc-empty">
            ${this.escapeHtml(r.message||r.reason||"Metrics unavailable.")}
          </div>
        </div>
      `;let a=t.metricsOverview?.()??{},c=a.metrics??{},n=a.metric_windows??{},s=t.metricsActiveTab?.()??"learning";return`
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
              ${this._renderMetricsStat("Jobs",c.job_count??0)}
              ${this._renderMetricsStat("Used",c.learning_used_count??0)}
              ${this._renderMetricsStat("Excluded",c.excluded_count??0)}
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
              ${this._renderMetricsTabContent(s,t,c,n)}
            </div>
          </section>
        </div>
      </div>
    `},i._renderMetricsTabContent=function(e,t,r,a){switch(e){case"rooms":return this._renderMetricsRoomsTab(t);case"profiles":return this._renderMetricsProfilesTab(t);case"water":return this._renderMetricsWaterTab(t,r);case"dock":return this._renderMetricsDockTab(r,t);case"battery":return this._renderMetricsBatteryTab(t);default:return this._renderMetricsLearningTab(t,r,a)}},i._renderMetricsLearningTab=function(e,t,r){let a=e.metricsFoundProfiles?.()??[],c=e.metricsLearningStats?.()??{},n=Array.isArray(c.exact)?c.exact.length:0,s=Array.isArray(c.baselines)?c.baselines.length:0,o=Array.isArray(c.accuracy)?c.accuracy.length:0;return`
      <div class="evcc-metrics-section-stack">
        <div class="evcc-metrics-window-grid">
          ${this._renderMetricsWindowCard("Today",r.today)}
          ${this._renderMetricsWindowCard("Last 7 Days",r.last_7_days)}
          ${this._renderMetricsWindowCard("Last 30 Days",r.last_30_days)}
        </div>

        <div class="evcc-metrics-card-grid">
          ${this._renderMetricsMiniCard("Found Profiles",a.length,"Profiles with learning history attached")}
          ${this._renderMetricsMiniCard("Exact Stats",n,"Exact room-learning stat groups")}
          ${this._renderMetricsMiniCard("Baselines",s,"Room baseline groups")}
          ${this._renderMetricsMiniCard("Accuracy Rows",o,"Accuracy stat rows")}
          ${this._renderMetricsMiniCard("Recharge Count",t.mid_job_recharge_count??0,"Observed mid-job recharges")}
          ${this._renderMetricsMiniCard("Wash Cycles",t.wash_cycle_count??0,"Wash cycles recorded from jobs")}
        </div>

        ${a.length?`
          <div class="evcc-metrics-card-grid">
            ${this._withDisambiguatedTitles(a).slice(0,8).map(l=>this._renderMetricsFoundProfileCard(l)).join("")}
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
            ${this._withDisambiguatedTitles(t).map(a=>this._renderMetricsRoomProfileCard(a)).join("")}
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
            ${this._withDisambiguatedTitles(r).slice(0,12).map(a=>this._renderMetricsFoundProfileCard(a)).join("")}
          </div>
        `:""}
      </div>
    `},i._renderMetricsWaterTab=function(e,t){let r=[...e.metricsRooms?.()??[]].sort((c,n)=>Number(n?.avg_total_water_used_ml??0)-Number(c?.avg_total_water_used_ml??0)).slice(0,8),a=[...e.metricsRoomProfiles?.()??[]].sort((c,n)=>Number(n?.avg_total_water_used_ml??0)-Number(c?.avg_total_water_used_ml??0)).slice(0,8);return`
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
            ${r.map(c=>this._renderMetricsWaterRoomCard(c)).join("")}
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
            ${a.map(c=>this._renderMetricsWaterProfileCard(c)).join("")}
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
    `},i._renderMetricsSelect=function(e,t,r,a,c){let n=Array.isArray(r)?r:[],s=[{value:"",label:c},...n.filter(o=>String(o?.value??"")!=="")];return`
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
    `},i._renderMetricsChipFilter=function(e,t,r,a,c){let s=(Array.isArray(r)?r:[]).filter(u=>u&&typeof u=="object").map(u=>({value:String(u?.value??""),label:String(u?.label??u?.value??""),title:String(u?.title??u?.label??u?.value??"")})),o=[{value:"",label:c},...s.filter(u=>u.value!=="")],l=t==="profile_key",d=l?`<div class="evcc-chip-filter-head">
           <div class="evcc-field-label">${this.escapeHtml(e)}</div>
           <input type="text" class="evcc-chip-search" data-chip-search placeholder="Search\u2026" aria-label="Search ${this.escapeHtml(e)}">
         </div>`:`<div class="evcc-field-label">${this.escapeHtml(e)}</div>`;return`
      <div class="evcc-metrics-chip-filter${l?" evcc-chip-filter--searchable":""}" data-chip-filter-group>
        ${d}
        <div class="evcc-chips evcc-metrics-filter-chips">
          ${o.map((u,m)=>`
            <button
              type="button"
              class="evcc-chip ${String(u.value)===String(a??"")?"active":""}"
              data-metrics-filter-chip="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(u.value)}"
              ${m===0?'data-all-chip="true"':""}
              title="${this.escapeHtml(u.title)}"
            >${this.escapeHtml(u.label)}</button>
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
    `},i._withDisambiguatedTitles=function(e){if(!Array.isArray(e)||!e.length)return Array.isArray(e)?e:[];let t=this.card?._state,r=a=>String(a?.profile_label||a?.selected_profile_label||a?.resolved_profile_label||a?.profile_key||"Profile");return t?._noteAmbiguousProfiles?.(e.map(r)),e.map(a=>{let c=r(a),n=String(a?.profile_subtitle??"").trim();return t?._isAmbiguousProfileLabel?.(c)&&n?{...a,display_title:`${c} \xB7 ${n}`,_settings_in_title:!0}:a})},i._renderMetricsRoomProfileCard=function(e){let t=e?.display_title||e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Profile",r=e?._settings_in_title?"":e?.profile_subtitle||e?.room_label||e?.room_slug||"",a=this.card?._state?.metricsProfileSaveKey?.("profile",e)??"",c=this.card?._state?.isMetricsProfileSavePending?.(a)??!1,n=e?.save_candidate===!0&&e?.save_supported===!0&&String(e?.save_service??"").trim()!=="";return`
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
        ${n?`
          <div class="evcc-metrics-card-actions">
            <button
              type="button"
              class="evcc-chip"
              data-metrics-save-profile="profile"
              data-profile-key="${this.escapeHtml(String(e?.profile_key??""))}"
              data-room-slug="${this.escapeHtml(String(e?.room_slug??""))}"
              ${c?"disabled":""}
              title="${this.escapeHtml(e?.save_suggested_label||"Save this learned profile")}"
            >${c?"Saving...":"Save Profile"}</button>
          </div>
        `:""}
      </div>
    `},i._renderMetricsFoundProfileCard=function(e){let t=e?.display_title||e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Profile",r=e?._settings_in_title?"":e?.profile_subtitle||e?.room_label||e?.room_slug||"",a=e?.trust_reason_text||e?.trust_reason||"",c=this.card?._state?.metricsProfileSaveKey?.("found",e)??"",n=this.card?._state?.isMetricsProfileSavePending?.(c)??!1,s=e?.save_candidate===!0&&String(e?.save_service??"").trim()!=="";return`
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
              ${n?"disabled":""}
              title="${this.escapeHtml(e?.save_suggested_label||"Save this learned profile")}"
            >${n?"Saving...":"Save Profile"}</button>
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
    `},i._formatMetricsDuration=function(e){let t=Number(e);return Number.isFinite(t)?this._formatLearningDuration(t):"0 min"},i._formatMetricsMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"0 ml"},i._formatMetricsTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatMetricsTrustLevel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())||"Unknown"},i._formatMetricsDurationValue=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:String(e??"Unknown")},i._renderMetricsBatteryTab=function(e){let t=e.batteryMetrics?.()??{},r=(g,R=2)=>{let y=Number(g);return Number.isFinite(y)?y.toFixed(R).replace(/\.?0+$/,""):"\u2014"},a=g=>{if(g==null)return!0;let R=String(g).trim().toLowerCase();return R===""||R==="unknown"||R==="unavailable"||R==="none"},c=(g,R=2,y="")=>{if(!g||a(g.state))return"\u2014";let T=Number(g.state);return Number.isFinite(T)?`${r(T,R)}${y}`:String(g.state)},n=`
      <div class="evcc-metrics-card-grid">
        ${this._renderMetricsMiniCard("Charge cycles",c(t.cycles,1),"Cumulative drain \xF7 100")}
        ${this._renderMetricsMiniCard("Health %",c(t.health,0,"%"),t.health?.attrs?.baseline_session_count?`vs first ${t.health.attrs.baseline_session_count} full charges`:"Building baseline")}
        ${this._renderMetricsMiniCard("Charge rate",c(t.rate_overall,2," %/min"),t.rate_overall?.attrs?.charging?"Charging now":"Last sample")}
        ${this._renderMetricsMiniCard("Last job %/m\xB2",c(t.last_job_per_m2,3),t.last_job_per_m2?.attrs?.area_m2?`${r(t.last_job_per_m2.attrs.area_m2,1)} m\xB2 | ${r(t.last_job_per_m2.attrs.battery_used_pct,0)} % used`:"Awaiting first job")}
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
            <td>${this.escapeHtml(c(t.rate_overall,2," %/min"))}</td>
            <td>Any active charge interval</td>
          </tr>
          <tr>
            <td>Low (\u2264 29 %)</td>
            <td>${this.escapeHtml(c(t.rate_low,2," %/min"))}</td>
            <td>Slow precharge / soft-cell signal</td>
          </tr>
          <tr>
            <td>High (\u2265 80 %)</td>
            <td>${this.escapeHtml(c(t.rate_high,2," %/min"))}</td>
            <td>CV taper \u2014 earliest health drop indicator</td>
          </tr>
          <tr>
            <td>Mid-job (15\u219275)</td>
            <td>${this.escapeHtml(c(t.rate_mid_job,2," %/min"))}</td>
            <td>${this.escapeHtml(`Rolling mean | ${t.rate_mid_job?.attrs?.sample_count??0} samples`)}</td>
          </tr>
          <tr>
            <td>Last full session</td>
            <td>${this.escapeHtml(c(t.last_charge_duration,0," min"))}</td>
            <td>${this.escapeHtml(t.last_charge_duration?.attrs?.last_charge_delta_pct!=null?`Charged ${t.last_charge_duration.attrs.last_charge_delta_pct} %`:"")}</td>
          </tr>
        </tbody>
      </table>
    `,o=t.last_job_per_m2?.attrs?.by_clean_mode_mean??{},l=t.last_job_per_m2?.attrs?.by_fan_speed_mean??{},d=t.last_job_per_m2?.attrs?.by_water_level_mean??{},u=(g,R)=>{let y=Object.keys(g||{});return y.length?y.map(T=>`
        <tr>
          <td>${this.escapeHtml(T)}</td>
          <td>${this.escapeHtml(r(g[T]?.mean,3))}</td>
          <td>${this.escapeHtml(String(g[T]?.count??0))}</td>
        </tr>
      `).join(""):`<tr><td colspan="3"><em>${this.escapeHtml(R)} \u2014 no single-bucket jobs yet</em></td></tr>`},m=t.last_job_per_m2?.attrs?.all_jobs_count??0,p=t.last_job_per_m2?.attrs?.all_jobs_mean,v=`
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
            <td>${this.escapeHtml(r(p,3))}</td>
            <td>${this.escapeHtml(String(m))}</td>
          </tr>
          <tr><td colspan="3"><em>By clean mode</em></td></tr>
          ${u(o,"Clean mode")}
          <tr><td colspan="3"><em>By fan speed</em></td></tr>
          ${u(l,"Fan speed")}
          <tr><td colspan="3"><em>By water level</em></td></tr>
          ${u(d,"Water level")}
        </tbody>
      </table>
    `,f=t.last_job_per_m2?.attrs??{},h=f.post_job_charge??null,b=f.recorded_at?`
      <div class="evcc-metrics-section-title">Most recent completed job</div>
      <table class="evcc-metrics-table">
        <tbody>
          <tr><td>Job ID</td><td>${this.escapeHtml(String(f.job_id??"\u2014"))}</td></tr>
          <tr><td>Recorded</td><td>${this.escapeHtml(this._formatMetricsTimestamp(f.recorded_at)||"\u2014")}</td></tr>
          <tr><td>Duration</td><td>${this.escapeHtml(r(f.duration_min,1)+" min")}</td></tr>
          <tr><td>Area</td><td>${this.escapeHtml(r(f.area_m2,1)+" m\xB2")}</td></tr>
          <tr><td>Battery used</td><td>${this.escapeHtml(r(f.battery_used_pct,0)+" %")}</td></tr>
          <tr><td>Drain rate</td><td>${this.escapeHtml(c(t.last_job_per_min,2," %/min"))}</td></tr>
          <tr><td>Drain per hour</td><td>${this.escapeHtml(c(t.last_job_per_hour,1," %/h"))}</td></tr>
          <tr><td>Drain per m\xB2</td><td>${this.escapeHtml(c(t.last_job_per_m2,3," %/m\xB2"))}</td></tr>
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
    `,w=e.vacuumObjectId?.()??"",S=`
      <div class="evcc-metrics-section-title">Raw data files</div>
      <div class="evcc-metrics-section-subtitle">
        Long-term review is best done from the raw files written by the integration.
        Chart any of the sensors above with HA's history-graph or apexcharts-card; for
        deeper analysis open the CSV in a spreadsheet.
      </div>
      <pre class="evcc-metrics-codeblock">config/eufy_vacuum/battery/${this.escapeHtml(w)}/sessions.csv
config/eufy_vacuum/battery/${this.escapeHtml(w)}/samples.jsonl</pre>
    `;return`
      <div class="evcc-metrics-section-stack">
        ${n}
        ${s}
        ${v}
        ${b}
        ${S}
      </div>
    `}}function Pa(i){i.renderLearningReviewView=function(e){let{state:t}=e,r=this._renderReviewSubtabStrip(t),a=t.reviewSubtab()==="external"?this.renderExternalJobsSubtab(e):this._renderLearningHistoryView(e);return`<div class="evcc-review-shell">${r}${a}</div>`},i._renderLearningHistoryView=function(e){let{state:t}=e,r=t.learningHistorySnapshot?.();if(!r)return'<div class="evcc-empty">Loading learning history...</div>';if(r.available===!1)return`
        <div class="evcc-review-view">
          <div class="evcc-empty">
            ${this.escapeHtml(r.message||r.reason||"Learning history unavailable.")}
          </div>
        </div>
      `;let a=r.summary??{},c=this._getSortedLearningReviewJobs(t,r.jobs??[]);return`
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
              ${this._renderReviewChipFilter("Room","room_slug",t.learningHistoryRooms?.().map(n=>({value:n?.room_slug??n?.slug??"",label:n?.room_name??n?.label??n?.slug??"Room"})),t.learningHistoryFilters?.().room_slug,"All Rooms")}

              ${this._renderReviewChipFilter("Profile","profile_key",t.learningHistoryProfiles?.().map(n=>({value:n?.profile_key??"",label:n?.label??n?.profile_key??"Profile",title:n?.subtitle?`${n?.label??n?.profile_key??"Profile"} | ${n.subtitle}`:n?.label??n?.profile_key??"Profile"})),t.learningHistoryFilters?.().profile_key,"All Profiles")}

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

            ${c.length?`
              <div class="evcc-review-job-list">
                ${c.map(n=>this._renderLearningReviewJobCard(n,t)).join("")}
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
    `},i._renderReviewSelect=function(e,t,r,a,c,n=!1){let s=Array.isArray(r)?r:[],o=s.length?s:[{value:"",label:c}],l=n?o:[{value:"",label:c},...o.filter(d=>String(d?.value??"")!=="")];return`
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
    `},i._renderReviewChipFilter=function(e,t,r,a,c,n="",s=!0){let l=(Array.isArray(r)?r:[]).filter(p=>p&&typeof p=="object").map(p=>({value:String(p?.value??""),label:String(p?.label??p?.value??""),title:String(p?.title??p?.label??p?.value??"")})),d=s?[{value:String(n),label:c},...l.filter(p=>p.value!==String(n))]:l,u=t==="profile_key",m=u?`<div class="evcc-chip-filter-head">
           <div class="evcc-field-label">${this.escapeHtml(e)}</div>
           <input type="text" class="evcc-chip-search" data-chip-search placeholder="Search\u2026" aria-label="Search ${this.escapeHtml(e)}">
         </div>`:`<div class="evcc-field-label">${this.escapeHtml(e)}</div>`;return`
      <div class="evcc-review-chip-filter${u?" evcc-chip-filter--searchable":""}" data-chip-filter-group>
        ${m}
        <div class="evcc-chips evcc-review-filter-chips">
          ${d.map((p,v)=>`
            <button
              type="button"
              class="evcc-chip ${String(p.value)===String(a??"")?"active":""}"
              data-review-filter-chip="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(p.value)}"
              ${v===0&&s?'data-all-chip="true"':""}
              title="${this.escapeHtml(p.title)}"
            >${this.escapeHtml(p.label)}</button>
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
              ${r.map(c=>`
                <button
                  type="button"
                  class="evcc-chip ${String(a)===String(c.profile_key)?"active":""}"
                  data-review-matcher-profile="${this.escapeHtml(c.profile_key)}"
                  title="Filter learning jobs to this profile"
                >${this.escapeHtml(c.label??c.profile_key)}</button>
              `).join("")}
            </div>
          `:`
            <div class="evcc-review-empty">Adjust the matcher fields until they line up with a saved profile exactly.</div>
          `}
        </div>
      </div>
    `},i._renderReviewMatcherField=function(e,t,r,a){let c=(Array.isArray(a)?a:[]).map(n=>n&&typeof n=="object"&&"value"in n?{value:n.value,label:n.label??n.value}:{value:n,label:n}).filter(n=>n.value!=null&&String(n.value).trim()!=="");return c.length?`
      <div class="evcc-editor-field-group evcc-review-matcher-field">
        <div class="evcc-field-label">${this.escapeHtml(e)}</div>
        <div class="evcc-chips">
          ${c.map(n=>`
            <button
              type="button"
              class="evcc-chip ${String(n.value)===String(r)?"active":""}"
              data-review-matcher-field="${this.escapeHtml(t)}"
              data-value="${this.escapeHtml(String(n.value))}"
            >${this.escapeHtml(String(n.label))}</button>
          `).join("")}
        </div>
      </div>
    `:""},i._renderReviewReasonChips=function(e,t,r){let a=t.learningHistoryExcludeReason?.(e);return`
      <div class="evcc-review-reason-chips">
        <div class="evcc-field-label">Exclude Reason</div>
        <div class="evcc-chips evcc-review-filter-chips">
          ${(t.learningHistoryExcludeReasonOptions?.()??[]).map(n=>`
            <button
              type="button"
              class="evcc-chip ${String(n?.value??"")===String(a??"")?"active":""}"
              data-review-reason-chip="${this.escapeHtml(e)}"
              data-value="${this.escapeHtml(String(n?.value??""))}"
              ${r?"disabled":""}
            >${this.escapeHtml(String(n?.label??n?.value??""))}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderLearningReviewJobCard=function(e,t){let r=String(e?.job_id??""),a=t.isLearningHistoryJobActionPending?.(r)??!1,c=e?.exclude_allowed===!0,n=e?.restore_allowed===!0,s=e?.excluded_from_learning===!0,o=[];s&&o.push({text:"Excluded",cls:"evcc-review-badge--excluded"}),e?.exclude_suggested===!0&&o.push({text:e?.exclude_suggested_reason_label||"Suggested Exclude",cls:"evcc-review-badge--suggested"}),String(e?.status??"").trim().toLowerCase()!=="completed"&&o.push({text:e?.status_label||this._formatReviewLabel(e?.status||"Unknown"),cls:"evcc-review-badge--warning"}),e?.sanity_passed===!1&&o.push({text:"Sanity Failed",cls:"evcc-review-badge--warning"}),e?.mid_job_recharge_observed===!0&&o.push({text:"Recharge",cls:"evcc-review-badge--neutral"}),e?.is_single_room===!0&&o.push({text:"Single Room",cls:"evcc-review-badge--neutral"}),e?.is_multi_room===!0&&o.push({text:"Multi Room",cls:"evcc-review-badge--neutral"});let l=[this._formatReviewTimestamp(e?.started_at),Number.isFinite(Number(e?.duration_minutes))?`${Number(e.duration_minutes).toFixed(1).replace(/\.0$/,"")} min`:"",Number.isFinite(Number(e?.outlier_score))?`Outlier ${Number(e.outlier_score).toFixed(2)}`:"",Number.isFinite(Number(e?.battery_used))?`Battery ${Number(e.battery_used)}`:"",Number.isFinite(Number(e?.total_water_used_ml))&&Number(e.total_water_used_ml)>0?`Water ${Math.round(Number(e.total_water_used_ml))} ml`:""].filter(Boolean),d=e?.exclude_suggested_reason_text||e?.exclude_reason_text||e?.restore_reason_text||e?.status_text||(Array.isArray(e?.learning_blocker_texts)&&e.learning_blocker_texts.length?e.learning_blocker_texts.join(", "):"")||(Array.isArray(e?.sanity_flag_texts)&&e.sanity_flag_texts.length?e.sanity_flag_texts.join(", "):"")||e?.cancel_detection?.reason_text||e?.exclude_suggested_reason_label||e?.exclude_reason_label||e?.restore_reason_label||(Array.isArray(e?.learning_blockers)&&e.learning_blockers.length?e.learning_blockers.join(", "):"")||(Array.isArray(e?.sanity_flags)&&e.sanity_flags.length?e.sanity_flags.join(", "):""),u=e?.profile_label||e?.selected_profile_label||e?.resolved_profile_label||e?.profile_key||"Unknown",m=String(e?.profile_subtitle??"").trim(),p=!!(this.card?._state?._isAmbiguousProfileLabel?.(u)&&m),v=p?`${u} \xB7 ${m}`:u,f=p?null:e?.profile_subtitle||null,h=Array.isArray(e?.room_slugs)&&e.room_slugs.length?e.room_slugs.join(", "):"Unknown",b=e?.primary_room_label||e?.primary_room_slug||"Unknown",w=e?.job_scope_label||(e?.job_scope?this._formatReviewLabel(e.job_scope):"Unknown");return`
      <article class="evcc-review-job-card ${s?"evcc-review-job-card--excluded":""} ${e?.exclude_suggested?"evcc-review-job-card--suggested":""}">
        <div class="evcc-review-job-header">
          <div>
            <div class="evcc-review-job-title">${this.escapeHtml(r)}</div>
            <div class="evcc-review-job-subtitle">${this.escapeHtml(l.join(" | "))}</div>
          </div>
          <div class="evcc-review-job-badges">
            ${o.map(S=>`
              <span class="evcc-chip ${S.cls}">${this.escapeHtml(S.text)}</span>
            `).join("")}
          </div>
        </div>

        <div class="evcc-review-job-grid">
          ${this._renderReviewKeyValue("Rooms",h)}
          ${this._renderReviewKeyValue("Scope",w)}
          ${this._renderReviewKeyValue("Profile",v,f)}
          ${this._renderReviewKeyValue("Used For Learning",e?.used_for_learning===!0?"Yes":"No")}
          ${this._renderReviewKeyValue("Primary Room",b)}
        </div>

        ${d?`
          <div class="evcc-review-job-note">${this.escapeHtml(d)}</div>
        `:""}

        <div class="evcc-review-job-actions">
          ${c?`
            ${this._renderReviewReasonChips(r,t,a)}
            <button
              type="button"
              class="evcc-chip"
              data-review-action="exclude"
              data-job-id="${this.escapeHtml(r)}"
              ${a?"disabled":""}
            >${a?"Working...":"Exclude"}</button>
          `:""}

          ${n?`
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
    `},i._getSortedLearningReviewJobs=function(e,t){let r=Array.isArray(t)?[...t]:[],a=e.learningHistorySort?.()??"newest";return a==="outlier"?r.sort((c,n)=>Number(n?.outlier_score??0)-Number(c?.outlier_score??0)):a==="suggested"?r.filter(c=>c?.exclude_suggested===!0).sort((c,n)=>Number(n?.outlier_score??0)-Number(c?.outlier_score??0)):a==="excluded"?r.filter(c=>c?.excluded_from_learning===!0).sort((c,n)=>new Date(n?.started_at??0).getTime()-new Date(c?.started_at??0).getTime()):r.sort((c,n)=>new Date(n?.started_at??0).getTime()-new Date(c?.started_at??0).getTime())},i._formatReviewTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")},i._formatReviewLabel=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())}}function Na(i){i.renderRoomsView=function(e){let{state:t}=e,r=t.getRoomsForActiveMap(),a=this._withCurrentRoomPinned(r,t),c=t.canStartCleaning(),n=t.startBlockedReason(),s=t.hasStartWarning(),o=t.enabledRoomCount(),l=t.activeJobRooms();return r.length===0?`
        <div class="evcc-rooms-view">
          <div class="evcc-empty">
            No rooms found. Run the discover rooms service to get started.
          </div>
        </div>
      `:`
      <div class="evcc-rooms-view">

        ${this.renderRoomsActionBar(c,n,o,r,s)}

        ${typeof this.renderLearningSummary=="function"?this.renderLearningSummary(t):""}

        ${typeof this.renderIncompleteRunBanner=="function"?this.renderIncompleteRunBanner(t):""}

        ${typeof this.renderLearningPreJobPanel=="function"?this.renderLearningPreJobPanel(t):""}

        ${typeof this.renderLearningLiveBanner=="function"?this.renderLearningLiveBanner(t):""}

        ${l?this.renderActiveJobSection(l):""}

        ${typeof this.renderLearningProgressList=="function"?this.renderLearningProgressList(t):""}

        ${this._renderOrphanedRoomsPanel(t)}

        <div class="evcc-rooms-workspace">
          <div class="evcc-rooms-main">

            ${this._renderRoomsViewToggle(t)}

            ${t.isMapViewActive?.()?typeof this.renderMapRoomView=="function"?this.renderMapRoomView(e):"":`<div class="evcc-room-grid">
                   ${a.map(d=>this.renderRoomCard(d,t)).join("")}
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
        <button
          class="evcc-rooms-view-toggle-btn${e.roomFloorTextureEnabled?.()??!0?" active":""}"
          data-action="room-texture-toggle"
          title="${e.roomFloorTextureEnabled?.()??!0?"Hide room-card textures":"Show room-card textures"}"
          aria-label="${e.roomFloorTextureEnabled?.()??!0?"Hide room-card textures":"Show room-card textures"}"
          aria-pressed="${e.roomFloorTextureEnabled?.()??!0?"true":"false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
            <rect x="2.5" y="3.5" width="11" height="9" rx="2"/>
            <path d="M4.5 9.5 L7.5 6.5 M7 11 L11 7 M9.5 11 L12 8.5"/>
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
          ${(window.AnimalSVG?.list?.()??["cat","dog","raccoon","parrot","snake"]).map(a=>{let n=window.AnimalSVG?.get?.(a)?.label??a.charAt(0).toUpperCase()+a.slice(1).replace(/_/g," "),s=e.mapAnimalSelection?.()??"cat";return`<option value="${a}"${s===a?" selected":""}>${n}</option>`}).join("")}
        </select>
        <input
          type="range"
          class="evcc-rooms-animal-scale"
          data-action="map-animal-scale"
          min="0.5" max="3" step="0.25"
          value="${e.mapAnimalScale?.()??1}"
          title="Icon size"
          aria-label="Icon size"
        >
        <button
          class="evcc-rooms-view-toggle-btn${e.mapAnimalEnabled?.()??!0?" active":""}"
          data-action="map-animal-toggle"
          title="${e.mapAnimalEnabled?.()??!0?"Hide companion":"Show companion"}"
          aria-label="${e.mapAnimalEnabled?.()??!0?"Hide companion":"Show companion"}"
          aria-pressed="${e.mapAnimalEnabled?.()??!0?"true":"false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" stroke="none">
            <ellipse cx="8" cy="10.5" rx="3" ry="2.3"/>
            <circle cx="3.8" cy="7" r="1.3"/>
            <circle cx="6.5" cy="4.8" r="1.3"/>
            <circle cx="9.5" cy="4.8" r="1.3"/>
            <circle cx="12.2" cy="7" r="1.3"/>
          </svg>
        </button>
        <button
          class="evcc-rooms-view-toggle-btn${e.mapFloorTextureEnabled?.()??!0?" active":""}"
          data-action="map-texture-toggle"
          title="${e.mapFloorTextureEnabled?.()??!0?"Hide map textures":"Show map textures"}"
          aria-label="${e.mapFloorTextureEnabled?.()??!0?"Hide map textures":"Show map textures"}"
          aria-pressed="${e.mapFloorTextureEnabled?.()??!0?"true":"false"}"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
            <rect x="2" y="2" width="12" height="12" rx="1.5"/>
            <path d="M2 6 L6 2 M2 10 L10 2 M2 14 L14 2 M6 14 L14 6 M10 14 L14 10"/>
          </svg>
        </button>`:""}
      </div>
    `},i._withCurrentRoomPinned=function(e,t){if(!Array.isArray(e)||e.length<2)return e;let r=this.card?._learningController;if(!r?.getRoomProgressSnapshot||!t?.hasActiveRun?.())return e;let a=e.findIndex(s=>!!r.getRoomProgressSnapshot(s.id)?.isCurrent);if(a<1)return e;let c=e.slice(),[n]=c.splice(a,1);return c.unshift(n),c},i._renderOrphanedRoomsPanel=function(e){let t=e.orphanedRooms?.()??[];return t.length?`
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
    `:""},i.renderRoomsActionBar=function(e,t,r,a,c){let n=r===1?"1 room":`${r} rooms`,s=(Array.isArray(a)?a:[]).filter(E=>E.enabled),o=e?c?"evcc-chip--start-warn":"evcc-chip--start":"disabled",l=this.card?._state,d=!!l?.hasActiveRun?.(),u=Number(this.card?._learningController?.getJobProgressPercent?.()??0),m=Array.isArray(l?.learningRoomTimeline?.())?l.learningRoomTimeline():[],p=l?.learningCompletedRooms?.()||[],v=new Set(p.map(E=>String(E.room_id))),f=s.reduce((E,q)=>{let U=String(q.id),j=m.find(ce=>String(ce.room_id)===U),pe=this.card?._state?.roomEstimateForRoom?.(q.id)??null,le=Number(j?.minutes??pe?.minutes);return Number.isFinite(le)?E+le:E},0),h=Number(l?.dashboardPlannedJobEstimateTotalMinutes?.()),b=Number.isFinite(h)&&h>0?h:f,w=b>0?this._formatLearningDuration(b):null,S=l?.startConfirmation?.()??null,g=l?.startPreflight?.()??S?.preflight??null,R=!!l?.startRequiresConfirmation?.(),y=!!l?.cancelRunRequiresConfirmation?.(),T=!!l?.clearQueueRequiresConfirmation?.(),M=!!l?.hasActiveRun?.(),J=!!l?.canPauseRun?.(),z=!!l?.canResumeRun?.(),he=y?"Confirm Cancel":M?"Cancel Run":R?"Confirm Start":"Start Cleaning",B=y?"evcc-chip--start-warn evcc-chip--confirm-flash":M?"evcc-chip--cancel-run":R?"evcc-chip--start-warn evcc-chip--confirm-flash":o,Se=R||y,ie=Array.isArray(g?.blocked_rooms)?g.blocked_rooms:[],de=Array.isArray(g?.modified_rooms)?g.modified_rooms:[],fe=Array.isArray(g?.warnings)?g.warnings:[],ge=l?.startMopCarpetWarning?.()??null,be=l?.startOrderAdvisory?.()??null;return`
    <div class="evcc-rooms-action-bar">

      <div class="evcc-rooms-bar-top">
        <div class="evcc-rooms-queue-summary">
          <span class="evcc-rooms-queue-count">${this.escapeHtml(n)}</span>
          <span class="evcc-rooms-queue-label">included</span>
          ${w?`
            <span class="evcc-rooms-queue-label">\xB7 ~${this.escapeHtml(w)}</span>
          `:""}
        </div>

        <div class="evcc-chips">
          <button
            type="button"
            class="evcc-chip ${B}"
            data-action="primary-room-action"
            ${!M&&!R&&!e?"disabled":""}
            title="${this.escapeHtml(t??"")}"
          >${this.escapeHtml(he)}</button>

          ${M&&(J||z)?`
            <button
              type="button"
              class="evcc-chip"
              data-action="${z?"resume-run":"pause-run"}"
            >${z?"Resume":"Pause"}</button>
          `:""}

          <button type="button" class="evcc-chip" data-action="locate-vacuum">
            Locate
          </button>

          <button type="button" class="evcc-chip" data-action="select-all">
            Select All
          </button>

          <button
            type="button"
            class="evcc-chip ${T?"evcc-chip--start-warn evcc-chip--confirm-flash":""}"
            data-action="clear-queue"
          >${T?"Confirm Clear":"Clear Queue"}</button>
        </div>
      </div>

      ${t&&!e?`
        <div class="evcc-rooms-block-reason">${this.escapeHtml(t)}</div>
      `:""}

      ${y?`
        <div class="evcc-rooms-cancel-warning" role="alert">
          Tap "Confirm Cancel" again to send the vacuum back to the dock,
          or press <strong>Cancel</strong> to keep the job running.
        </div>
      `:""}

      ${ge?`
        <div class="evcc-rooms-carpet-warning" role="alert">
          \u26A0 ${this.escapeHtml(ge)}
        </div>
      `:""}

      ${be?`
        <div class="evcc-rooms-order-advisory">
          ${this.escapeHtml(be)}
        </div>
      `:""}

      ${Se?`
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

          ${ie.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Blocked Rooms</div>
              <div class="evcc-start-preflight-list">
                ${ie.map(E=>`
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-room">${this.escapeHtml(E.name??E.room_id??"Room")}</span>
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(E.reason??"Blocked")}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          `:""}

          ${de.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Modified Rooms</div>
              <div class="evcc-start-preflight-list">
                ${de.map(E=>{let q=Object.keys(E.changes??{}).join(", ")||"Settings adjusted",U=E.derived&&E.source_rule_name?` (via ${E.source_room_name??"another room"}'s ${E.source_rule_name})`:"";return`
                    <div class="evcc-start-preflight-item">
                      <span class="evcc-start-preflight-room">${this.escapeHtml(E.name??E.room_id??"Room")}</span>
                      <span class="evcc-start-preflight-reason">${this.escapeHtml(q+U)}</span>
                    </div>
                  `}).join("")}
              </div>
            </div>
          `:""}

          ${fe.length?`
            <div class="evcc-start-preflight-section">
              <div class="evcc-start-preflight-title">Warnings</div>
              <div class="evcc-start-preflight-list">
                ${fe.map(E=>`
                  <div class="evcc-start-preflight-item">
                    <span class="evcc-start-preflight-reason">${this.escapeHtml(E)}</span>
                  </div>
                `).join("")}
              </div>
            </div>
          `:""}
        </div>
      `:""}

      ${s.length>0?`
        <div class="evcc-queue-chips">

          ${s.map((E,q)=>{let U=String(E.id),j=m.find($e=>String($e.room_id)===U),pe=v.has(U),le=this.card?._learningController?.getRoomProgressSnapshot?.(E.id)??null,ce="evcc-queue-chip--queued";d&&(j?.completed||pe||le?.isCompleted?ce="evcc-queue-chip--completed":j?.current||le?.isCurrent?ce="evcc-queue-chip--current":j?.skipped||le?.isSkipped?ce="evcc-queue-chip--skipped":(j?.remaining||j)&&(ce="evcc-queue-chip--remaining"));let Le=j?.running_long||le?.isRunningLong?"evcc-queue-chip--running-long":"",Te="";if(j?.confidence_breakpoint?.ui_variant){let $e=j.confidence_breakpoint.ui_variant;$e==="success"?Te="evcc-queue-chip--confidence-high":$e==="warning"?Te="evcc-queue-chip--confidence-medium":$e==="error"&&(Te="evcc-queue-chip--confidence-low")}let Pe=j?.minutes!=null?this._formatLearningMinutes(j.minutes):null,Re=ce==="evcc-queue-chip--completed"?100:ce==="evcc-queue-chip--current"?Number(le?.percent??u):0,Ue=ce==="evcc-queue-chip--current"?`${Math.max(0,Math.min(99,Math.floor(Re)))}%`:Pe;return`
              <button
                type="button"
                class="evcc-queue-chip ${ce} ${Te} ${Le}"
                data-queue-chip="true"
                data-room-id="${E.id}"
                data-map-id="${this.escapeHtml(E.mapId)}"
                data-enabled="${E.enabled?"true":"false"}"
                style="--job-progress:${Re}%;"
                title="Click for settings \xB7 Double-click for estimate \xB7 Hold to remove from queue"
                aria-label="Queue room ${this.escapeHtml(E.name)}"
              >
                <span class="evcc-queue-chip-order">${q+1}</span>

                <span class="evcc-queue-chip-label">
                  ${this.escapeHtml(E.name)}
                </span>

                ${Ue?`
                  <span class="evcc-queue-chip-time">
                    ${this.escapeHtml(Ue)}
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
  `},i.renderRoomCard=function(e,t){let r=this._normalizeRoomDisplayData(e),a=r.cleanMode?r.cleanModeLabel||this._formatCleanMode(r.cleanMode):null,n=!r.fanSpeed||["off","normal"].includes(String(r.fanSpeed).toLowerCase())?null:r.fanSpeedLabel||this._formatFanSpeed(r.fanSpeed),o=!r.cleanIntensity||String(r.cleanIntensity).toLowerCase()==="standard"?null:r.cleanIntensityLabel||this._formatCleanIntensity(r.cleanIntensity),l=this._isMopMode(r.cleanMode)&&r.waterLevel&&String(r.waterLevel).toLowerCase()!=="off"?r.waterLevelLabel||this._formatWaterLevel(r.waterLevel):null,d=this._isMopMode(r.cleanMode)&&r.edgeMopping?"Edge Mop On":null,u=Number(r.cleanPasses)>1?`${Number(r.cleanPasses)}\xD7 passes`:null,m=this.card?._state?.orderDragItemId?.(),p=this.card?._state?.orderDragOverItemId?.(),v=String(m)===String(r.id)?"evcc-order-drag-source":"",f=String(p)===String(r.id)?"evcc-order-drag-target":"",h=t?.roomEstimateForRoom?.(r.id)??null,b=t?.dashboardPlannedWaterRoomForRoom?.(r.id,r.slug)??null,w="";if(h&&h.error==null){let E=h.source==="learned"?"evcc-room-status--estimate-learned":"evcc-room-status--estimate-default",q=h.source==="learned"?this._formatLearningMinutes(h.minutes):`~${this._formatLearningMinutes(h.minutes)}`,U=[`Estimate: ${this._formatLearningMinutes(h.minutes)}`];h.source&&U.push(`Source: ${String(h.source)}`);let j=Number(h.battery);Number.isFinite(j)&&U.push(`Battery: ${j}`);let pe=U.join(" \xB7 ");w=`
      <div
        class="evcc-room-status evcc-room-status--estimate ${E}"
        title="${this.escapeHtml(pe)}"
      >
        ${this.escapeHtml(q)}
      </div>
    `}let S="",g="",R="";if(h&&h.error==null&&typeof this.renderConfidenceChip=="function")if(h.source==="learned"){let E=h?.confidence_breakpoint?.ui_variant,q=E==="success"?"Reliable":E==="warning"?"Learning":E==="error"?"Uncertain":null;q&&(S=this.renderConfidenceChip(h.confidence_breakpoint,q,q),E==="success"?g="evcc-room-card--confidence-high":E==="warning"?g="evcc-room-card--confidence-medium":g="evcc-room-card--confidence-low")}else h.source==="default"&&(S=this.renderConfidenceChip({ui_variant:"neutral"},"Unlearned","Unlearned"));let y=String(b?.effective_clean_mode??b?.clean_mode??"").toLowerCase(),T=String(b?.effective_water_level??b?.water_level??"").toLowerCase();if(!!(b?.mop_active||this._isMopMode(y))&&T!=="off"){let E=Number(b.estimated_robot_water_used_ml);Number.isFinite(E)&&(R=`
        <div
          class="evcc-room-status"
          title="${this.escapeHtml([`Projected water use: ~${Math.round(E)} ml`,b?.clean_mode_label?`Mode: ${String(b.clean_mode_label)}`:b?.effective_clean_mode?`Mode: ${String(b.effective_clean_mode)}`:null,b?.water_level_label?`Water: ${String(b.water_level_label)}`:b?.effective_water_level?`Water: ${String(b.effective_water_level)}`:null].filter(Boolean).join(" \xB7 "))}"
        >
          ${this.escapeHtml(`~${Math.round(E)} ml water`)}
        </div>
      `)}let J=[];h?.intensity_mismatch&&J.push({text:"\u26A0 intensity mismatch",variant:"warning"});let z=t?.troubleRoomForRoom?.(r.id)??null;if(z?.is_trouble){let E=Number(z.miss_count??0),q=Number(z.run_count??0),U=Number(z.miss_rate??0),j=Number.isFinite(U)?Math.round(U*100):null;J.push({text:`\u26A0 Missed ${E}\xD7 of ${q} run${q===1?"":"s"}${j!==null?` (${j}%)`:""}`,variant:"warning",title:`This room was missed in ${j??"?"}% of recent runs. Consider checking for obstacles or map accuracy.`})}let he=!!this.card?._state?.hasActiveRun?.(),B=this.card?._learningController?.getRoomProgressSnapshot?.(r.id)??null,Se=B?.percent??this.card?._learningController?.getRoomProgressPercent?.(r.id),ie=Number.isFinite(Se)?Se:0,de="evcc-room-card--queue-idle";r.enabled&&he&&(B?.isCompleted||ie>=100?de="evcc-room-card--queue-completed":B?.isCurrent||ie>0?de="evcc-room-card--queue-current":de="evcc-room-card--queue-remaining");let fe="",ge=this.formatRelativeAgo?.(r.lastCleanedAt);if(ge&&!B?.isCurrent){let E=[`Last cleaned: ${r.lastCleanedAt}`];r.lastJobMode&&E.push(`Mode: ${String(r.lastJobMode)}`),fe=`
      <div
        class="evcc-room-status evcc-room-status--last-cleaned"
        title="${this.escapeHtml(E.join(" | "))}"
      >${this.escapeHtml(ge)}</div>
    `}let be=he&&B&&B.isCurrent?`
        <div class="evcc-room-progress-meta">
          <div
            class="evcc-room-status evcc-room-progress-chip"
            title="${this.escapeHtml([`Progress: ${B.percent}%`,Number.isFinite(B.elapsedMinutes)?`Elapsed: ${this._formatLearningMinutes(B.elapsedMinutes)}`:"",Number.isFinite(B.remainingMinutes)?`Remaining: ${this._formatLearningMinutes(B.remainingMinutes)}`:""].filter(Boolean).join(" \xB7 "))}"
          >
            ${this.escapeHtml(`${B.percent}% complete`)}
          </div>

          ${Number.isFinite(B.remainingMinutes)?`
            <div
              class="evcc-room-status evcc-room-progress-chip evcc-room-progress-chip--remaining"
              title="${this.escapeHtml([`Progress: ${B.percent}%`,Number.isFinite(B.elapsedMinutes)?`Elapsed: ${this._formatLearningMinutes(B.elapsedMinutes)}`:"",`Remaining: ${this._formatLearningMinutes(B.remainingMinutes)}`].filter(Boolean).join(" \xB7 "))}"
            >
              ${this.escapeHtml(`~${this._formatLearningMinutes(B.remainingMinutes)} left`)}
            </div>
          `:""}
        </div>
      `:"";return`
    <div
      class="evcc-room-card ${r.enabled?"is-enabled":"is-disabled"} ${v} ${f} ${de} ${g}"
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
      style="--room-progress:${ie}%;"
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

      ${a||n||o||l||d||u?`
        <div class="evcc-room-setting-chips">
          ${a?`<span class="evcc-room-setting-chip">${this.escapeHtml(a)}</span>`:""}
          ${n?`<span class="evcc-room-setting-chip">${this.escapeHtml(n)}</span>`:""}
          ${o?`<span class="evcc-room-setting-chip">${this.escapeHtml(o)}</span>`:""}
          ${l?`<span class="evcc-room-setting-chip">${this.escapeHtml(l)}</span>`:""}
          ${d?`<span class="evcc-room-setting-chip">${this.escapeHtml(d)}</span>`:""}
          ${u?`<span class="evcc-room-setting-chip">${this.escapeHtml(u)}</span>`:""}
        </div>
      `:""}

      ${be}

      <div class="evcc-room-chip-row">

        ${w}

        ${S}

        ${R}

        ${fe}

      </div>

      ${J.length?`
        <div class="evcc-room-notes">
          ${J.map(E=>`
            <div
              class="evcc-room-note evcc-room-note--${this.escapeHtml(E.variant)}"
              ${(()=>{let q=String(E.text).includes("No learned data")?"This room is using a fallback estimate until enough learned samples are collected.":String(E.text).includes("runs to reliable")?`Estimated ${String(E.text).split(" ")[0]} more runs to reach high confidence.`:String(E.text).includes("intensity mismatch")?"Estimate was learned from a different cleaning intensity or profile.":"",U=E.title||q;return U?`title="${this.escapeHtml(U)}"`:""})()}
            >
              ${this.escapeHtml(E.text)}
            </div>
          `).join("")}
        </div>
      `:""}

    </div>
  `},i._normalizeRoomDisplayData=function(e){let t=e?.selected_profile_details??{},r=String(e?.profile_name??e?.profileName??e?.profile??"vacuum_quick"),a=String(e?.clean_mode??e?.cleanMode??t?.clean_mode??"vacuum"),c=String(e?.fan_speed??e?.fanSpeed??t?.fan_speed??""),n=String(e?.water_level??e?.waterLevel??t?.water_level??""),s=String(e?.clean_intensity??e?.cleanIntensity??t?.clean_intensity??""),o=Number(e?.clean_passes??e?.cleanPasses??e?.passes??t?.default_clean_passes??1),l=!!(e?.edge_mopping??e?.edgeMopping??t?.default_edge_mopping??!1),d=String(e?.floor_type??e?.floorType??""),u=String(e?.carpet_type??e?.carpetType??""),m=!!(e?.carpet??(()=>{let v=String(d).toLowerCase();return v==="carpet"||v.startsWith("carpet_")||v.startsWith("carpet-")})()),p=Number(e?.order??e?.displayOrder??e?.position??999999);return{id:e?.id,mapId:e?.mapId??e?.map_id??"",name:e?.name??e?.room_name??"",slug:e?.slug??e?.room_slug??null,enabled:!!e?.enabled,order:Number.isFinite(p)?p:999999,profileName:r,profileLabel:e?.profile_label??e?.profileLabel??e?.selected_profile_label??e?.resolved_profile_label??null,profileSubtitle:e?.profile_subtitle??e?.profileSubtitle??null,lastCleanedAt:e?.lastCleanedAt??e?.last_cleaned_at??null,lastJobMode:e?.lastJobMode??e?.last_job_mode??null,isCustomProfile:r.toLowerCase()==="custom",cleanMode:a,cleanModeLabel:e?.clean_mode_label??e?.cleanModeLabel??t?.clean_mode_label??null,fanSpeed:c,fanSpeedLabel:e?.fan_speed_label??e?.fanSpeedLabel??t?.fan_speed_label??null,waterLevel:n,waterLevelLabel:e?.water_level_label??e?.waterLevelLabel??t?.water_level_label??null,cleanIntensity:s,cleanIntensityLabel:e?.clean_intensity_label??e?.cleanIntensityLabel??t?.clean_intensity_label??t?.path_type_label??null,cleanPasses:Number.isFinite(o)?o:1,cleanPassesLabel:e?.clean_passes_label??e?.cleanPassesLabel??t?.clean_passes_label??null,edgeMopping:l,edgeMoppingLabel:e?.edge_mopping_label??e?.edgeMoppingLabel??t?.edge_mopping_label??null,floorType:d,floorTypeLabel:e?.floor_type_label??e?.floorTypeLabel??null,carpetType:u,carpetTypeLabel:e?.carpet_type_label??e?.carpetTypeLabel??null,carpet:m,selectedProfileDetails:t}},i._isMopMode=function(e){let t=String(e??"").toLowerCase();return t==="mop"||t==="vacuum_mop"||t.includes("mop")||t.includes("wash")},i._roomProfileLabel=function(e){let t=String(e??"").trim();return t?t.toLowerCase()==="custom"?"Custom":t==="vacuum_quick"?"Vacuum Only Quick":t==="vacuum_deep"?"Vacuum Only Deep":t==="vacuum_mop_quick"?"Quick":t==="vacuum_mop_deep"?"Deep":t==="user_1"?"User Profile 1":t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):"Standard"},i._formatCleanMode=function(e){let t=String(e??"").trim().toLowerCase();return t==="vacuum_mop"||t==="vacuum and mop"?"Vacuum + Mop":t==="vacuum"?"Vacuum":t==="mop"?"Mop":this._formatSettingValue(e)},i._formatFanSpeed=function(e){return this._formatSettingValue(e)},i._formatWaterLevel=function(e){return this._formatSettingValue(e)},i._formatCleanIntensity=function(e){return this._formatSettingValue(e)},i._formatFloorType=function(e){return this._formatSettingValue(e)},i._formatSettingValue=function(e){return e?String(e).replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase()):""}}function Fa(i){i.renderRunProfilesPanel=function(e){let t=e.savedRunProfiles?.()??[],r=e.selectedRunProfile?.()??null,a=e.runProfileDraft?.()??{name:"",expose_as_button:!1},c=!!e.isRunProfileEditorOpen?.(),n=e.runProfileEditorMode?.()??"new";return`
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

        ${c?`
          <div class="evcc-run-profiles-editor">
            <div class="evcc-run-profiles-editor-title">
              ${n==="edit"?"Edit Saved Profile":"Create Run Profile"}
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
                data-action="${n==="edit"?"overwrite-run-profile":"save-new-run-profile"}"
              >${n==="edit"?"Save Over Profile":"Create Profile"}</button>

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
    `}}function Da(i){i.renderMaintenanceView=function(e){let{state:t}=e,r=t.dashboardUpkeep?.()??{},a=r.attention_summary??t.dashboardAttentionSummary?.(),c=t.dashboardStatusSummary?.(),n=r.model_meta??{},s=Array.isArray(r.replacement_items)?r.replacement_items:[],o=Array.isArray(r.maintenance_items)?r.maintenance_items:[],l=Number(r.attention_count??0),d=r.highest_priority_status_label??r.highest_priority_status??null,u=r.updated_at??null,m=t.maintenanceActiveTab?.()??"maintenance_items",p=m==="replacements"?s:o,v=m==="replacements"?"Replacement Items":"Maintenance Items",f=m==="replacements"?"Upstream replacement-style items":"Integration-managed maintenance intervals",h=[...o.map(M=>({...M,_category:"Maintenance"})),...s.map(M=>({...M,_category:"Replacement"}))].filter(M=>this._maintenanceItemNeedsAttention(M)),b=r.station_water??null,S=(t.dashboardPlannedWaterEstimate?.()??null)?.available_clean_tank_ml??null,g=n.name??null,R=n.guide_family_name??null,y=s.filter(M=>this._maintenanceItemNeedsAttention(M)).length,T=o.filter(M=>this._maintenanceItemNeedsAttention(M)).length;return`
      <div class="evcc-maintenance-view">
        <div class="evcc-maintenance-grid">

          <section class="evcc-maintenance-panel">
            <div class="evcc-maintenance-panel-header">
              <div>
                <div class="evcc-maintenance-panel-title">Maintenance Overview</div>
                <div class="evcc-maintenance-panel-subtitle">
                  ${this.escapeHtml(a||c||"Backend maintenance snapshot")}
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
              ${this._renderMaintenanceStat("Water",r.station_water_label??b??"Unknown")}
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
              ${this._renderMaintenanceStat("Attention",y)}
              ${this._renderMaintenanceStat("Healthy",Math.max(s.length-y,0))}
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
                  ${h.map(M=>this._renderMaintenanceAttentionItem(M)).join("")}
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
                class="evcc-chip evcc-maintenance-tab ${m==="maintenance_items"?"active":""}"
                data-maintenance-tab="maintenance_items"
                role="tab"
                aria-selected="${m==="maintenance_items"?"true":"false"}"
              >
                Maintenance Items
              </button>

              <button
                type="button"
                class="evcc-chip evcc-maintenance-tab ${m==="replacements"?"active":""}"
                data-maintenance-tab="replacements"
                role="tab"
                aria-selected="${m==="replacements"?"true":"false"}"
              >
                Replacements
              </button>
            </div>

            <div class="evcc-maintenance-tab-panel">
              <div class="evcc-maintenance-tab-header">
                <div class="evcc-maintenance-panel-title">${this.escapeHtml(v)}</div>
                <div class="evcc-maintenance-panel-subtitle">${this.escapeHtml(f)}</div>
              </div>

              ${p.length?`<div class="evcc-maintenance-card-grid">
                    ${p.map(M=>this._renderMaintenanceCard(M)).join("")}
                    ${m==="maintenance_items"?this._renderStationWaterCard(b,S,r.station_water_label):""}
                   </div>`:`<div class="evcc-maintenance-empty">No ${m==="replacements"?"replacement":"maintenance"} items reported.</div>`}
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
    `},i._renderMaintenanceCard=function(e){let t=e?.label??e?.component_label??e?.name??e?.title??"Unnamed item",r=String(e?.kind??"maintenance"),a=String(e?.status??"unknown"),c=e?.status_label??this._formatMaintenanceStatus(a),n=e?.available!==!1,s=this._maintenanceRemainingPercent(e),o=Number.isFinite(s)?Math.max(0,Math.min(100,s)):0,l=this._maintenancePrimaryValue(e),d=this._maintenanceSecondaryValue(e),u=this._maintenanceDueInLabel(e),m=e?.guide?.display??null,p=m?.frequency||this._formatMaintenanceFrequency(m?.frequency);return`
      <button
        type="button"
        class="evcc-maintenance-card evcc-maintenance-card--status-${this.escapeHtml(a)} ${n?"":"evcc-maintenance-card--unavailable"}"
        data-action="open-maintenance-modal"
        data-item-kind="${this.escapeHtml(r)}"
        data-item-component="${this.escapeHtml(String(e?.component??""))}"
        data-item-entity-id="${this.escapeHtml(String(e?.entity_id??""))}"
        style="--maintenance-remaining:${o}%;"
      >
        <div class="evcc-maintenance-card-header">
          <div class="evcc-maintenance-card-title">${this.escapeHtml(t)}</div>
          <div class="evcc-maintenance-card-status">${this.escapeHtml(c)}</div>
        </div>

        <div class="evcc-maintenance-card-value">
          ${this.escapeHtml(l)}
        </div>

        ${u?`
          <div class="evcc-maintenance-card-due">${this.escapeHtml(u)}</div>
        `:""}

        <div class="evcc-maintenance-card-detail">
          ${this.escapeHtml([e?.kind_label??this._formatMaintenanceKind(r),d].filter(Boolean).join(" | "))}
        </div>

        ${p?`
          <div class="evcc-maintenance-card-secondary">
            ${this.escapeHtml(p)}
          </div>
        `:""}
      </button>
    `},i._renderStationWaterCard=function(e,t=null,r=null){let a=e!=null&&e!=="",c=Number(e),n=Number.isFinite(c),s=String(r??"").trim()||(a?n?`${Math.round(c)}%`:String(e):"Unknown"),o=String(s).trim().toLowerCase(),l="unknown";n?c>=70?l="good":c>=35?l="warning":c>0?l="replace_soon":l="replace_now":["full","high","good","ok","normal"].includes(o)?l="good":["medium","mid"].includes(o)?l="warning":["low","empty","none"].includes(o)&&(l="replace_soon");let d=n?c>=70?"High":c>=35?"Medium":c>0?"Low":"Empty":String(r??"").trim()||this._formatMaintenanceStatus(l),u=n?Math.max(0,Math.min(100,c)):l==="good"?100:l==="warning"?55:l==="replace_soon"?20:0;return`
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
    `},i.renderMaintenanceItemModal=function(e){let t=e?.state,r=t?.activeMaintenanceModalItem?.();if(!r)return"";let a=r?.label??r?.component_label??r?.name??r?.title??"Item details",c=String(r?.kind??"maintenance"),n=String(r?.status??"unknown"),s=r?.status_label??this._formatMaintenanceStatus(n),o=this._maintenancePrimaryValue(r),l=this._maintenanceSecondaryValue(r),d=r?.guide?.display??null,u=Array.isArray(d?.steps)?d.steps.filter(Boolean):[],m=Array.isArray(d?.notes)?d.notes.filter(Boolean):[],p=t?.maintenanceResetUi?.()??{},v=t?.canInvokeMaintenanceReset?.(r)??!1,f=String(r?.reset_kind??"").trim().toLowerCase(),h=!!p?.pending,b=!!p?.confirming,w=String(p?.success??""),S=String(p?.error??"");return`
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
            <div class="evcc-maintenance-modal-hero evcc-maintenance-modal-hero--status-${this.escapeHtml(n)}">
              <div class="evcc-maintenance-modal-hero-top">
                <div class="evcc-maintenance-modal-hero-label">${this.escapeHtml(r?.kind_label??this._formatMaintenanceKind(c))}</div>
                <div class="evcc-maintenance-modal-hero-status">${this.escapeHtml(s)}</div>
              </div>

              <div class="evcc-maintenance-modal-hero-value">${this.escapeHtml(o)}</div>

              ${l?`
                <div class="evcc-maintenance-modal-hero-detail">${this.escapeHtml(l)}</div>
              `:""}

              ${(()=>{let g=this._maintenanceDueInLabel(r);return g?`<div class="evcc-maintenance-modal-hero-due">${this.escapeHtml(g)}</div>`:""})()}
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

            ${m.length?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Notes</div>
                <div class="evcc-maintenance-guide-notes">
                  ${m.map(g=>`
                    <div class="evcc-maintenance-guide-note">${this.escapeHtml(g)}</div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${c==="maintenance"?(()=>{let g=Number(r?.interval_hours),R=Number(r?.default_interval_hours),y=Number(r?.max_interval_hours),T=r?.reset_service_data?.vacuum_entity_id??"",M=r?.component??"",J=Number.isFinite(g)&&g>0?g:Number.isFinite(R)?R:"",z=[];return Number.isFinite(R)&&R>0&&z.push(`Default ${R}h`),Number.isFinite(y)&&y>0&&z.push(`Max ${y}h`),`
                <div class="evcc-editor-field-group">
                  <div class="evcc-field-label">Interval</div>
                  <div class="evcc-maintenance-interval-row">
                    <input
                      type="number"
                      class="evcc-maintenance-interval-input"
                      data-role="maintenance-interval-input"
                      min="1"
                      ${Number.isFinite(y)&&y>0?`max="${y}"`:""}
                      step="0.5"
                      value="${this.escapeHtml(String(J))}"
                      data-default="${this.escapeHtml(String(R||0))}"
                      data-vacuum-entity-id="${this.escapeHtml(String(T))}"
                      data-component="${this.escapeHtml(String(M))}"
                    />
                    <span class="evcc-maintenance-interval-unit">hours</span>
                    <button
                      type="button"
                      class="evcc-chip evcc-chip--save"
                      data-action="save-maintenance-interval"
                    >Save</button>
                    ${Number.isFinite(R)&&R>0?`
                      <button
                        type="button"
                        class="evcc-chip"
                        data-action="reset-maintenance-interval-default"
                        title="Restore manufacturer default (${R}h)"
                      >Default</button>
                    `:""}
                  </div>
                  ${z.length?`
                    <div class="evcc-maintenance-interval-hint">${this.escapeHtml(z.join(" \xB7 "))}</div>
                  `:""}
                </div>
              `})():""}

            ${v?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">Reset</div>

                ${w?`
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--success">
                    ${this.escapeHtml(w)}
                  </div>
                `:""}

                ${S?`
                  <div class="evcc-maintenance-reset-hint evcc-maintenance-reset-hint--error">
                    ${this.escapeHtml(S)}
                  </div>
                `:""}

                ${b?`
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
    `},i._maintenanceItemNeedsAttention=function(e){if(!e||typeof e!="object")return!1;if(e.needs_attention===!0||e.attention_required===!0||e.warning===!0||e.overdue===!0||e.due===!0)return!0;let t=String(e?.status??"").trim().toLowerCase();if(["warning","replace_soon","replace_now"].includes(t))return!0;let r=Number(e.remaining_percent);return!!(Number.isFinite(r)&&r<=20)},i._maintenanceRemainingPercent=function(e){let t=Number(e?.remaining_percent);if(Number.isFinite(t))return t;let r=Number(e?.remaining_hours),a=Number(e?.kind==="replacement"?e?.max_life_hours??e?.total_life_hours:e?.interval_hours);return Number.isFinite(r)&&Number.isFinite(a)&&a>0?r/a*100:null},i._maintenanceDueInLabel=function(e){if(!e||e.kind!=="maintenance")return null;let t=Number(e.remaining_hours),r=Number(e.used_since_reset_hours),a=e.reset_at;if(!Number.isFinite(t)||!Number.isFinite(r)||!a)return null;let c=Date.parse(String(a));if(!Number.isFinite(c))return null;let n=(Date.now()-c)/864e5;if(!Number.isFinite(n)||n<3)return null;let s=r/n;if(!Number.isFinite(s)||s<.1)return null;if(t<=0)return"Overdue";let o=t/s;return Number.isFinite(o)?o<1?"Due today":o<2?"Due tomorrow":o<14?`Due in ~${Math.round(o)} days`:o<60?`Due in ~${Math.round(o/7)} weeks`:`Due in ~${Math.round(o/30)} months`:null},i._maintenancePrimaryValue=function(e){let t=String(e?.remaining_summary??"").trim();if(t)return t;let r=this._maintenanceRemainingPercent(e);if(Number.isFinite(r))return`${Math.round(r)}% remaining`;let a=Number(e?.remaining_hours);if(Number.isFinite(a))return`${this._formatMaintenanceHours(a)} remaining`;let c=e?.remaining_value,n=e?.remaining_unit;return c!=null?[c,n].filter(Boolean).join(" "):"Unknown remaining life"},i._maintenanceSecondaryValue=function(e){let t=String(e?.usage_summary??"").trim();if(t)return t;if(e?.kind==="replacement"){let n=Number(e?.usage_hours),s=Number(e?.max_life_hours??e?.total_life_hours);if(Number.isFinite(n)&&Number.isFinite(s))return`${this._formatMaintenanceHours(n)} used of ${this._formatMaintenanceHours(s)}`}let r=Number(e?.remaining_hours),a=Number(e?.interval_hours);if(Number.isFinite(r)&&Number.isFinite(a))return`${this._formatMaintenanceHours(r)} left of ${this._formatMaintenanceHours(a)}`;let c=Number(e?.used_since_reset_hours??e?.current_usage_hours);return Number.isFinite(c)?`${this._formatMaintenanceHours(c)} used since reset`:""},i._formatMaintenanceHours=function(e){let t=Number(e);if(!Number.isFinite(t))return"0 hours";let r=t.toFixed(1).replace(/\.0$/,""),c=Number(r)===1?"hour":"hours";return`${r} ${c}`},i._formatMaintenanceFrequency=function(e){let t=String(e??"").trim();return t?t.replace(/[_-]+/g," ").replace(/\b\w/g,r=>r.toUpperCase()):""},i._formatMaintenanceKind=function(e){return String(e??"").replace(/[_-]+/g," ").replace(/\b\w/g,t=>t.toUpperCase())},i._formatMaintenanceStatus=function(e){let t=String(e??"").trim().toLowerCase();return t==="replace_now"?"Replace Now":t==="replace_soon"?"Replace Soon":t==="warning"?"Warning":t==="good"?"Good":t==="unknown"?"Unknown":this._formatMaintenanceKind(t||"unknown")},i._formatMaintenanceTimestamp=function(e){return this.formatTimestamp(e,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"},"")}}function Ha(i){i.renderRoomAccessModal=function(e){let{state:t}=e;if(!t.isRoomAccessOpen?.())return"";let r=t.activeAccessRoom?.();if(!r)return"";let a=t.accessEditableRooms?.()??[],c=t.accessInboundRooms?.()??[],n=new Set(t.roomAccessFields?.().grants_access_to??[]),s=t.roomAccessValidation?.()??{valid:!0,issues:[]},o=t.roomAccessSaveError?.(),l=t.roomAccessFields?.().is_dock_room??!1;return`
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
                ${a.length?a.map(d=>{let u=n.has(d.id),m=d.available!==!1,p=d.claimedBy??null,v=p?`Already claimed by Room ${p}`:"";return`
                        <button
                          type="button"
                          class="evcc-chip evcc-room-access-chip
                            ${u?"active":""}
                            ${d.missing?"evcc-room-access-chip--missing":""}
                            ${m?"":"evcc-room-access-chip--claimed"}"
                          data-action="toggle-room-access-target"
                          data-room-id="${this.escapeHtml(d.id)}"
                          ${m?"":"disabled"}
                          ${v?`title="${this.escapeHtml(v)}"`:""}
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
                ${c.length?c.map(d=>`
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
    `}}function za(i){i.renderRoomEstimateModal=function(e){let{state:t}=e;if(!t.isRoomEstimateModalOpen?.())return"";let r=t.activeRoomEstimateDetails?.(),a=r?.room??null;if(!a)return"";let c=r.entry??null,n=r.roomEstimate??null,s=r.plannedWaterRoom??null,o=this.card?._learningController?.getRoomProgressSnapshot?.(a.id)??null,l=Number(c?.minutes??n?.minutes),d=c?.eta_at??n?.eta_at??null,u=Number(n?.sample_count),m=Number(n?.battery),p=Number(s?.estimated_robot_water_used_ml),v=Number.isFinite(p),f=[];n?.intensity_mismatch&&f.push("Estimated from different intensity"),n?.source==="default"&&f.push("No learned data yet"),Number(n?.learning_velocity?.runs_to_high??0)>0&&f.push(`${n.learning_velocity.runs_to_high} runs to reliable`);let h=[Number.isFinite(l)?{label:"Estimated time",value:this._formatLearningMinutes(l)}:null,d?{label:"Done by",value:this._formatLearningWallClock(d)}:null,n?.source?{label:"Source",value:String(n.source)}:null,Number.isFinite(u)?{label:"Samples",value:String(u)}:null,Number.isFinite(m)?{label:"Battery",value:String(m)}:null].filter(Boolean),b=[v?{label:"Projected water",value:`~${Math.round(p)} ml`}:null,s?.clean_mode_label?{label:"Mode",value:String(s.clean_mode_label)}:s?.effective_clean_mode?{label:"Mode",value:String(s.effective_clean_mode)}:null,s?.water_level_label?{label:"Water level",value:String(s.water_level_label)}:s?.effective_water_level?{label:"Water level",value:String(s.effective_water_level)}:null].filter(Boolean),w=o?[{label:"Progress",value:`${Math.max(0,Math.min(100,Number(o.percent??0)))}%`},Number.isFinite(o.elapsedMinutes)?{label:"Elapsed",value:this._formatLearningMinutes(o.elapsedMinutes)}:null,Number.isFinite(o.remainingMinutes)?{label:"Remaining",value:this._formatLearningMinutes(o.remainingMinutes)}:null].filter(Boolean):[],S=[];return Number.isFinite(l)&&S.push(this._formatLearningMinutes(l)),d&&S.push(`done by ${this._formatLearningWallClock(d)}`),`
      <div class="evcc-modal-backdrop" data-action="close-room-estimate">
        <div class="evcc-modal evcc-room-estimate-modal" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title-group">
              <div class="evcc-modal-title">${this.escapeHtml(a.name)} Estimate</div>
              ${S.length?`
                <div class="evcc-room-estimate-subtitle">${this.escapeHtml(S.join(" - "))}</div>
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

            ${b.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Water Projection</div>
                <div class="evcc-room-estimate-grid">
                  ${b.map(g=>`
                    <div class="evcc-room-estimate-row">
                      <span>${this.escapeHtml(g.label)}</span>
                      <span>${this.escapeHtml(g.value)}</span>
                    </div>
                  `).join("")}
                </div>
              </div>
            `:""}

            ${w.length?`
              <div class="evcc-room-estimate-section">
                <div class="evcc-field-label">Live Progress</div>
                <div class="evcc-room-estimate-grid">
                  ${w.map(g=>`
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
    `}}function Ba(i){i.renderRoomEditorModal=function(e){let{state:t}=e;if(!t.isRoomEditorOpen())return"";let r=t.activeEditorRoom(),a=t.editorFields();if(!r||!a)return"";let c=t.isEditorRoomCarpet();return`
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

          ${c?`
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

            ${t.supportsRoomProfiles()?this._renderProfileSelector(t,r,a):""}
            ${this._renderCleanModeField(t,a)}
            ${this._renderMopStateIndicator(t)}
            ${this._renderSuctionField(t,a)}
            ${t.showWaterLevel()?this._renderWaterLevelField(t,a):""}
            ${this._renderIntensityField(t,a)}
            ${this._renderPassesField(a,t.maxCleanPasses(),t.passesIsGlobal())}
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
    `},i._renderProfileSelector=function(e,t,r){let a=e.isCustomProfile(),c=e.roomProfilesList?.()??[],n=e.currentEditorManagedProfileName?.(),s=n?e.roomProfileDefinition?.(n):null,o=n?e.isProtectedRoomProfile?.(n):!1,l=(e.customRoomProfiles?.()??[]).length>0;return c.length===0?"":`
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

          ${c.map(d=>`
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
            ${n&&s&&!o?"":"disabled"}
          >Rename</button>

          <button
            type="button"
            class="evcc-chip evcc-chip--danger"
            data-action="delete-room-profile"
            ${n&&s&&!o?"":"disabled"}
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
              class="evcc-chip ${t.clean_mode===a.value?"active":""}"
              data-field="clean_mode"
              data-value="${this.escapeHtml(a.value)}"
            >${this.escapeHtml(a.label)}</button>
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
              class="evcc-chip ${t.fan_speed===a.value?"active":""}"
              data-field="fan_speed"
              data-value="${this.escapeHtml(a.value)}"
            >${this.escapeHtml(a.label)}</button>
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
              class="evcc-chip ${t.water_level===a.value?"active":""}"
              data-field="water_level"
              data-value="${this.escapeHtml(a.value)}"
            >${this.escapeHtml(a.label)}</button>
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
              class="evcc-chip ${t.clean_intensity===a.value?"active":""}"
              data-field="clean_intensity"
              data-value="${this.escapeHtml(a.value)}"
            >${this.escapeHtml(a.label)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderPassesField=function(e,t,r){let a=Math.max(1,Math.trunc(Number(t))||2),c=[];for(let s=1;s<=a;s+=1)c.push(`
          <button
            type="button"
            class="evcc-chip ${e.clean_passes===s?"active":""}"
            data-field="clean_passes"
            data-value="${s}"
          >${s} ${s===1?"Pass":"Passes"}</button>`);let n=r?`<div class="evcc-room-editor-field-note">
           Applies to the whole run \u2014 the highest passes across the selected rooms is used.
         </div>`:"";return`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Passes</div>
        <div class="evcc-chips">${c.join("")}</div>
        ${n}
      </div>
    `},i._renderMopStateIndicator=function(e){let t=e.mopActive();return t===null?"":`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">Cleaning Mode</div>
        <div class="evcc-room-editor-mopstate ${t?"mopping":"vacuum"}">
          ${t?"Mopping \u2014 water tank attached":"Vacuum only \u2014 no water tank"}
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
    `}}var fn=new Set(["is_on","is_off","exists","missing"]);function ja(i){i.renderRoomRulesView=function(e){let{state:t}=e,r=t.getRoomsForActiveMap?.()??[];if(!r.length)return`
        <div class="evcc-room-rules-view">
          <div class="evcc-empty">No rooms found. Run the discover rooms service to get started.</div>
        </div>
      `;let a=t.resolvedRoomRulesRoom?.(),c=t.roomRulesDraft?.(),n=t.roomRulesDraftMode?.(),s=t.roomRulesSaveError?.();return`
      <div class="evcc-room-rules-view">
        ${this._renderRoomRulesSubtabs(r,a)}
        <div class="evcc-room-rules-content">
          ${a?c?this._renderRuleEditor(t,a,c,n,s):this._renderRuleList(t,a):'<div class="evcc-empty">Select a room above.</div>'}
        </div>
      </div>
    `},i._renderRoomRulesSubtabs=function(e,t){return`
      <div class="evcc-room-rules-subtabs">
        ${[...e].sort((a,c)=>(a.order??0)-(c.order??0)).map(a=>{let c=t&&String(a.id)===String(t.id),n=Array.isArray(a.rules)?a.rules.length:0;return`
            <button
              type="button"
              class="evcc-room-rules-subtab ${c?"active":""}"
              data-action="set-room-rules-tab"
              data-room-id="${this.escapeHtml(String(a.id))}"
            >
              ${this.escapeHtml(a.name)}
              ${n?`<span class="evcc-room-rules-subtab-count">${n}</span>`:""}
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
    `},i._renderRuleCard=function(e,t){let r=e.ruleConditionSummary?.(t)??"",a=e.ruleEffectSummary?.(t)??"",c=t.label||t.entity_id||"Unnamed rule",n=t.kind==="blocker";return`
      <div class="evcc-rule-card ${t.enabled?"":"evcc-rule-card--disabled"}">
        <div class="evcc-rule-card-body">
          <span class="evcc-rule-kind-badge evcc-rule-kind-badge--${n?"blocker":"modifier"}">
            ${n?"Blocker":"Modifier"}
          </span>

          <div class="evcc-rule-info">
            <div class="evcc-rule-label">${this.escapeHtml(c)}</div>
            ${t.label?`<div class="evcc-rule-entity">${this.escapeHtml(t.entity_id)}</div>`:""}
            <div class="evcc-rule-condition">${this.escapeHtml(r)}</div>
            <div class="evcc-rule-effect">${this.escapeHtml(a)}</div>
            ${(()=>{let s=Array.isArray(t.fan_out_room_ids)?t.fan_out_room_ids.length:0;return s>0?`<div class="evcc-rule-fan-out">\u2192 also affects ${s} room${s===1?"":"s"}</div>`:""})()}
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
    `},i._renderRuleEditor=function(e,t,r,a,c){let n=a==="new",s=r.kind==="modifier",o=e.ruleEntityDescriptor?.(r)??null,l=e.ruleOperatorGroups?.(r)??[],d=e.ruleEntitySearchResults?.(r.entity_id,10)??[],u=fn.has(r.operator??""),m=e.roomRulesDraftIsValid?.()??!1;return`
      <div class="evcc-rule-editor">
        <div class="evcc-rule-editor-header">
          <div class="evcc-rule-editor-title">
            ${n?"New Rule":"Edit Rule"} - ${this.escapeHtml(t.name)}
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
            ${l.map(p=>`
              <div class="evcc-rule-operator-group">
                <div class="evcc-rule-operator-group-label">${this.escapeHtml(p.label)}</div>
                <div class="evcc-chips">
                  ${p.operators.map(v=>`
                    <button
                      type="button"
                      class="evcc-chip ${r.operator===v.value?"active":""}"
                      data-rule-field="operator"
                      data-rule-value="${this.escapeHtml(v.value)}"
                    >${this.escapeHtml(v.label)}</button>
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

          ${s?this._renderModifierChanges(r,e):""}

          ${s?this._renderRuleFanOutSection(r,e):""}
        </div>

        ${c?`<div class="evcc-rule-editor-save-error">${this.escapeHtml(c)}</div>`:""}

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
            ${m?"":"disabled"}
          >${n?"Add Rule":"Save Rule"}</button>
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
    `:'<div class="evcc-rule-entity-search-empty">No matching Home Assistant entities found.</div>'},i._renderRuleValueField=function(e,t,r){let a=r?.valueModeForOperator?.(t.operator)??"text",c=t.value;if(a==="single-select"&&r?.options?.length)return`
        <div class="evcc-rule-editor-section">
          <label class="evcc-field-label" for="rule-value-select">Value</label>
          <select
            id="rule-value-select"
            class="evcc-rule-editor-input"
            data-rule-select="value"
          >
            <option value="">Select a value</option>
            ${r.options.map(n=>`
              <option
                value="${this.escapeHtml(String(n.value))}"
                ${String(c??"")===String(n.value)?"selected":""}
              >${this.escapeHtml(n.label)}</option>
            `).join("")}
          </select>
        </div>
      `;if(a==="multi-select"&&r?.options?.length){let n=Array.isArray(c)?c.map(String):[];return`
        <div class="evcc-rule-editor-section">
          <div class="evcc-field-label">Value</div>
          <div class="evcc-chips">
            ${r.options.map(s=>`
              <button
                type="button"
                class="evcc-chip ${n.includes(String(s.value))?"active":""}"
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
            value="${this.escapeHtml(c==null?"":String(c))}"
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
          value="${this.escapeHtml(Array.isArray(c)?c.join(", "):String(c??""))}"
          data-rule-input="value"
        />
        ${t.operator==="in"||t.operator==="not_in"?'<div class="evcc-rule-editor-help">Comma-separated list of values.</div>':""}
      </div>
    `},i._renderRuleFanOutSection=function(e,t){let r=t.availableFanOutTargets?.()??[];if(!r.length)return"";let a=new Set((Array.isArray(e.fan_out_room_ids)?e.fan_out_room_ids:[]).map(c=>String(c)));return`
      <div class="evcc-rule-editor-section">
        <div class="evcc-field-label">Also apply to</div>
        <div class="evcc-rule-editor-help">
          When this rule fires, also apply its settings to the rooms below.
          Each room's own rules still win for any fields they set; this
          fills in fields the room hasn't already overridden.
        </div>
        <div class="evcc-chips">
          ${r.map(c=>`
            <button
              type="button"
              class="evcc-chip ${a.has(String(c.id))?"active":""}"
              data-rule-field="fan_out_room_ids"
              data-rule-value="${this.escapeHtml(String(c.id))}"
            >${this.escapeHtml(c.name)}</button>
          `).join("")}
        </div>
      </div>
    `},i._renderModifierChanges=function(e,t){let r=e.effect?.changes??{},a=(l,d,u)=>!Array.isArray(u)||u.length===0?"":`
        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">${this.escapeHtml(l)}</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${r[d]==null?"active":""}"
              data-rule-field="effect.changes.${this.escapeHtml(d)}"
              data-rule-value=""
            >-</button>
            ${u.map(m=>`
              <button
                type="button"
                class="evcc-chip ${r[d]===m.value?"active":""}"
                data-rule-field="effect.changes.${this.escapeHtml(d)}"
                data-rule-value="${this.escapeHtml(String(m.value))}"
              >${this.escapeHtml(m.label)}</button>
            `).join("")}
          </div>
        </div>
      `,c=t?.adapterOptionsFor?.("clean_mode")??[],n=t?.adapterOptionsFor?.("fan_speed")??[],s=t?.adapterOptionsFor?.("water_level")??[],o=t?.adapterOptionsFor?.("clean_intensity")??[];return`
      <div class="evcc-rule-editor-section">
        <div class="evcc-field-label">Setting Overrides</div>
        <div class="evcc-rule-editor-help">
          Select overrides to apply. "-" means keep the room's saved setting.
        </div>

        ${a("Clean Mode","clean_mode",c)}
        ${a("Fan Speed","fan_speed",n)}
        ${a("Water Level","water_level",s)}
        ${a("Clean Intensity","clean_intensity",o)}

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">Clean Passes</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${r.clean_passes==null?"active":""}"
              data-rule-field="effect.changes.clean_passes"
              data-rule-value=""
            >-</button>
            ${[1,2].map(l=>`
              <button
                type="button"
                class="evcc-chip ${r.clean_passes===l?"active":""}"
                data-rule-field="effect.changes.clean_passes"
                data-rule-value="${l}"
              >${l}</button>
            `).join("")}
          </div>
        </div>

        <div class="evcc-rule-change-row">
          <div class="evcc-rule-change-label">Edge Mopping</div>
          <div class="evcc-chips">
            <button
              type="button"
              class="evcc-chip evcc-chip--muted ${r.edge_mopping==null?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value=""
            >-</button>
            <button
              type="button"
              class="evcc-chip ${r.edge_mopping===!0?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="true"
            >On</button>
            <button
              type="button"
              class="evcc-chip ${r.edge_mopping===!1?"active":""}"
              data-rule-field="effect.changes.edge_mopping"
              data-rule-value="false"
            >Off</button>
          </div>
        </div>
      </div>
    `}}function Va(i){i.renderOrderSelectorModal=function(e){let{state:t}=e;if(!t.isOrderSelectorOpen())return"";let r=t.orderSelectorScope(),a=t.orderSelectorItem(),c=t.orderSelectorTargetPosition(),n=t.orderSelectorPositions(),s=t.getOrderAdapter(r);if(!a||!s)return"";let o=s.getLabel(a),l=String(s.getId(a)),d=t.getOrderedItemsForScope?.(r)??[],u=t.getOrderedItemPosition?.(r,l),m=c!=null&&Number(c)!==Number(u),p=m?t.previewMovedItemsForScope?.(r,l,c)??[]:[],v=f=>f.map((h,b)=>{let S=String(s.getId(h))===l,g=s.getLabel(h);return`
        <span class="evcc-order-preview-chip ${S?"evcc-order-preview-chip--active":""}">
          <span class="evcc-order-preview-chip-pos">${b+1}</span>
          ${this.escapeHtml(g)}
        </span>
      `}).join("");return`
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
              <div class="evcc-field-label">Currently</div>
              <div class="evcc-order-preview-row">
                ${v(d)}
              </div>
            </div>

            ${m?`
              <div class="evcc-editor-field-group">
                <div class="evcc-field-label">After move</div>
                <div class="evcc-order-preview-row">
                  ${v(p)}
                </div>
              </div>
            `:""}

            <div class="evcc-editor-field-group">
              <div class="evcc-field-label">Move to position</div>
              <div class="evcc-chips">
                ${n.map(f=>`
                  <button
                    type="button"
                    class="evcc-chip ${Number(c)===Number(f)?"active":""}"
                    data-action="set-order-position"
                    data-position="${f}"
                  >${f}</button>
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
              ${m?"":"disabled"}
            >Save</button>
          </div>

        </div>
      </div>
    `}}var P="/eufy_vacuum/textures",gn="1a193b54a5",wt=`?v=${gn}`,Oe={tile:{opacityDefault:1,layers:[{url:`${P}/tile/tile-mask.png`,role:"base",colorToken:"--evcc-floor-tile-base",colorDefault:"#D4AF37",opacityToken:"--evcc-floor-tile-face-opacity",opacityDefault:.87},{url:`${P}/tile/grout-mask.png`,role:"grout",colorToken:"--evcc-floor-tile-grout",colorDefault:"#121212",opacityToken:"--evcc-floor-tile-grout-opacity",opacityDefault:.95},{url:`${P}/tile/pure-tile-grout.png`,role:"accent",colorToken:"--evcc-floor-tile-accent",colorDefault:"#f0f0f5",opacityToken:"--evcc-floor-tile-line-opacity",opacityDefault:.39}],masks:[{url:`${P}/tile/tile-mask.png`},{url:`${P}/tile/grout-mask.png`},{url:`${P}/tile/pure-tile-grout.png`}],baseTexture:null},wood:{opacityDefault:.99,layers:[{url:`${P}/wood/wood-directional-depth-mask.png`,role:"base",colorToken:"--evcc-floor-wood-base",colorDefault:"#7A4010cf",opacityToken:"--evcc-floor-wood-depth-opacity",opacityDefault:.43},{url:`${P}/wood/wood-grain-mask.png`,role:"base",colorToken:"--evcc-floor-wood-base",colorDefault:"#7A4010cf",opacityToken:"--evcc-floor-wood-grain-opacity",opacityDefault:.84},{url:`${P}/wood/wood-seam-mask.png`,role:"accent",colorToken:"--evcc-floor-wood-accent",colorDefault:"#e89754",opacityToken:"--evcc-floor-wood-seam-opacity",opacityDefault:.78}],masks:[{url:`${P}/wood/wood-grain-mask.png`},{url:`${P}/wood/wood-seam-mask.png`},{url:`${P}/wood/wood-directional-depth-mask.png`}],baseTexture:null},marble:{opacityDefault:.9,layers:[{url:`${P}/marble/marble-base-mask.png`,role:"base",colorToken:"--evcc-floor-marble-base",colorDefault:"#e9e8e8",opacityToken:"--evcc-floor-marble-base-opacity",opacityDefault:.97},{url:`${P}/marble/marble-micro-texture-mask.png`,role:"micro",colorToken:"--evcc-floor-marble-micro",colorDefault:"#080707",opacityToken:"--evcc-floor-marble-micro-opacity",opacityDefault:1},{url:`${P}/marble/marble-vein-major.png`,role:"vein-major",colorToken:"--evcc-floor-marble-accent",colorDefault:"#D4AF3773",opacityToken:"--evcc-floor-marble-vein-major-opacity-eff",opacityDefault:"clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-major-opacity,0)),1)",blurToken:"--evcc-floor-marble-vein-major-blur-eff",blurDefault:"max(0px,calc(var(--evcc-floor-marble-vein-blur,0px) + var(--evcc-floor-marble-vein-major-blur,0px)))"},{url:`${P}/marble/marble-vein-minor.png`,role:"vein-minor",colorToken:"--evcc-floor-marble-vein-minor-color-eff",colorDefault:"oklch(from var(--evcc-floor-marble-accent,#D4AF3773) calc(l + var(--evcc-floor-marble-vein-minor-light,0.06)) calc(c * var(--evcc-floor-marble-vein-minor-chroma,0.65)) calc(h + var(--evcc-floor-marble-vein-minor-hue,6)) / alpha)",opacityToken:"--evcc-floor-marble-vein-minor-opacity-eff",opacityDefault:"clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(--evcc-floor-marble-vein-minor-opacity,-0.12)),1)",blurToken:"--evcc-floor-marble-vein-minor-blur-eff",blurDefault:"max(0px,calc(var(--evcc-floor-marble-vein-blur,0px) + var(--evcc-floor-marble-vein-minor-blur,1.5px)))"}],masks:[{url:`${P}/marble/marble-vein-major.png`},{url:`${P}/marble/marble-vein-minor.png`},{url:`${P}/marble/marble-micro-texture-mask.png`},{url:`${P}/marble/marble-base-mask.png`}],baseTexture:null},concrete:{opacityDefault:1,layers:[{url:`${P}/concrete/concrete-broad-mask.png`,role:"base",colorToken:"--evcc-floor-concrete-base",colorDefault:"#eceaea",opacityToken:"--evcc-floor-concrete-broad-opacity",opacityDefault:1},{url:`${P}/concrete/concrete-micro-mask.png`,role:"accent",colorToken:"--evcc-floor-concrete-accent",colorDefault:"#121111",opacityToken:"--evcc-floor-concrete-micro-opacity",opacityDefault:.62}],masks:[{url:`${P}/concrete/concrete-micro-mask.png`},{url:`${P}/concrete/concrete-broad-mask.png`}],baseTexture:null},carpet_low:{opacityDefault:.8,layers:[{url:`${P}/carpet/texture-floor-carpet-low.png`,role:"base",colorToken:"--evcc-floor-carpet-low-base",colorDefault:"#0d0c0c",opacityToken:"--evcc-floor-carpet-low-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${P}/carpet/texture-floor-carpet-low.png`},carpet_high:{opacityDefault:1,layers:[{url:`${P}/carpet/texture-floor-carpet-high.png`,role:"base",colorToken:"--evcc-floor-carpet-high-base",colorDefault:"#0a0a0a",opacityToken:"--evcc-floor-carpet-high-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${P}/carpet/texture-floor-carpet-high.png`},granite_light:{opacityDefault:1,layers:[{url:`${P}/granite/texture-floor-granite-light.png`,role:"base",colorToken:"--evcc-floor-granite-light-base",colorDefault:"#0a0a0a",opacityToken:"--evcc-floor-granite-light-texture-opacity",opacityDefault:1}],masks:[],baseTexture:`${P}/granite/texture-floor-granite-light.png`},default:{opacityDefault:.85,layers:[],masks:[],baseTexture:null}};for(let i of Object.values(Oe)){for(let e of i.layers)e.url&&(e.url+=wt);for(let e of i.masks)e.url&&(e.url+=wt);i.baseTexture&&(i.baseTexture+=wt)}function St(i){let e=Oe[i];return e?e.baseTexture?e.baseTexture:e.layers.length?e.layers[0].url:e.masks.length?e.masks[0].url:null:null}var Rt="--evcc-floor-";function Et(){return Object.keys(Oe).filter(i=>i!=="default").map(i=>i.replace(/_/g,"-")).sort()}function qa(i){return`${Rt}${i}-`}function bn(i,e){return typeof i=="string"&&i.startsWith(qa(e))}function _n(i,e){let t=null;for(let r of e)i.startsWith(qa(r))&&(!t||r.length>t.length)&&(t=r);return t}function Ga(i){let e=i&&typeof i=="object"&&i.theme||i||{},t=Et(),r=new Set,a=new Set;for(let c of["tokens","colors","alpha"]){let n=e[c];if(!(!n||typeof n!="object"))for(let s of Object.keys(n)){if(!s.startsWith(Rt))continue;let o=_n(s,t);if(o)r.add(o);else{let l=s.slice(Rt.length);a.add(l.split("-")[0]||l)}}}return{known:[...r].sort(),unknown:[...a].sort()}}function Ua(i,e){let t=i&&typeof i=="object"&&i.theme||{},r=(Array.isArray(e)?e:[e]).filter(Boolean),a=c=>{let n={};if(c&&typeof c=="object")for(let[s,o]of Object.entries(c))r.some(l=>bn(s,l))&&(n[s]=o);return n};return{ok:!0,version:i?.version??1,exported_at:i?.exported_at??null,scope:[...r],theme:{name:t.name??"",tokens:a(t.tokens),colors:a(t.colors),alpha:a(t.alpha)}}}function Wa(i){let e=i&&typeof i=="object"&&i.theme||{};return Object.keys(e.tokens||{}).length+Object.keys(e.colors||{}).length+Object.keys(e.alpha||{}).length}function Ja(i,e){let t=i&&typeof i=="object"&&i.theme||{},r=e||{},a=0,c=n=>{let s={};if(!n||typeof n!="object")return s;for(let[o,l]of Object.entries(n)){let d=r[o],u=d&&Number.isFinite(d.min)?d.min:null,m=d&&Number.isFinite(d.max)?d.max:null,p=Number(l);if((u!==null||m!==null)&&Number.isFinite(p)){let v=p;u!==null&&v<u&&(v=u),m!==null&&v>m&&(v=m),v!==p&&(a+=1),s[o]=v}else s[o]=l}return s};return{envelope:{...i,theme:{...t,tokens:c(t.tokens),colors:c(t.colors),alpha:c(t.alpha)}},corrected:a}}function kt(i,e,t,r){return{id:i,name:e,envelope:{ok:!0,version:1,scope:["marble"],name:e,theme:{name:e,tokens:t,colors:r,alpha:{}}}}}var Ze=[kt("carrara","Carrara",{"--evcc-floor-marble-opacity-card":.9,"--evcc-floor-marble-base-opacity":.97,"--evcc-floor-marble-micro-opacity":.45,"--evcc-floor-marble-vein-opacity":.5,"--evcc-floor-marble-vein-blur":.5,"--evcc-floor-marble-vein-major-opacity":-.4,"--evcc-floor-marble-vein-minor-opacity":.08,"--evcc-floor-marble-vein-major-blur":0,"--evcc-floor-marble-vein-minor-blur":1,"--evcc-floor-marble-vein-minor-light":.05,"--evcc-floor-marble-vein-minor-chroma":.55,"--evcc-floor-marble-vein-minor-hue":0},{"--evcc-floor-marble-base":"#f4f3f0","--evcc-floor-marble-micro":"#20201e","--evcc-floor-marble-accent":"#9a9a98"}),kt("portoro","Portoro",{"--evcc-floor-marble-opacity-card":.95,"--evcc-floor-marble-base-opacity":1,"--evcc-floor-marble-micro-opacity":.4,"--evcc-floor-marble-vein-opacity":.85,"--evcc-floor-marble-vein-blur":.5,"--evcc-floor-marble-vein-major-opacity":0,"--evcc-floor-marble-vein-minor-opacity":-.1,"--evcc-floor-marble-vein-major-blur":0,"--evcc-floor-marble-vein-minor-blur":1,"--evcc-floor-marble-vein-minor-light":.06,"--evcc-floor-marble-vein-minor-chroma":.7,"--evcc-floor-marble-vein-minor-hue":4},{"--evcc-floor-marble-base":"#14120e","--evcc-floor-marble-micro":"#0a0908","--evcc-floor-marble-accent":"#c9a24b"}),kt("calacatta","Calacatta",{"--evcc-floor-marble-opacity-card":.92,"--evcc-floor-marble-base-opacity":.97,"--evcc-floor-marble-micro-opacity":.4,"--evcc-floor-marble-vein-opacity":.7,"--evcc-floor-marble-vein-blur":.5,"--evcc-floor-marble-vein-major-opacity":.12,"--evcc-floor-marble-vein-minor-opacity":-.35,"--evcc-floor-marble-vein-major-blur":0,"--evcc-floor-marble-vein-minor-blur":1.5,"--evcc-floor-marble-vein-minor-light":.08,"--evcc-floor-marble-vein-minor-chroma":.55,"--evcc-floor-marble-vein-minor-hue":2},{"--evcc-floor-marble-base":"#f3f1eb","--evcc-floor-marble-micro":"#1c1a16","--evcc-floor-marble-accent":"#c9a24b"})];var yn="https://kingchddg901.github.io/Vacuum_Agent/";function Ka(i){if(!i)return null;let e=String(i).trim();if(!/^color-mix\(/i.test(e))return null;let t=e.indexOf("("),r=e.lastIndexOf(")");if(t===-1||r===-1)return null;let n=e.slice(t+1,r).replace(/^\s*in\s+\w+\s*,\s*/i,"").match(/^(.*?\s+\d+(?:\.\d+)?%)\s*,\s*(.*?\s+\d+(?:\.\d+)?%)\s*$/);if(!n)return null;let s=/^(.*?)\s+(\d+(?:\.\d+)?)%$/,o=n[1].trim().match(s),l=n[2].trim().match(s);return!o||!l?null:{color1:o[1].trim(),ratio:parseFloat(o[2]),color2:l[1].trim(),ratio2:parseFloat(l[2])}}function xn(i,e,t){let r=Math.max(0,Math.min(100,Math.round(e)));return`color-mix(in srgb, ${i} ${r}%, ${t} ${100-r}%)`}var et=new Set(["--evcc-accent","--evcc-surface-base","--evcc-text-primary","--evcc-radius-card"]),wn={"Shared Foundations":{min:0,max:64,step:2},"Cards & Surfaces":{min:0,max:32,step:1},"Borders & Shadows":{min:0,max:32,step:1},Chips:{min:20,max:48,step:1},"Room Cards":{min:0,max:32,step:1},"Floor Textures":{min:0,max:1,step:.01},"Floor Textures \u2014 Tile":{min:0,max:1,step:.01},"Floor Textures \u2014 Wood":{min:0,max:1,step:.01},"Floor Textures \u2014 Marble":{min:0,max:1,step:.01},"Floor Textures \u2014 Concrete":{min:0,max:1,step:.01},"Floor Textures \u2014 Carpet Low":{min:0,max:1,step:.01},"Floor Textures \u2014 Carpet High":{min:0,max:1,step:.01},"Floor Textures \u2014 Granite":{min:0,max:1,step:.01},"Queue & Ordering":{min:0,max:32,step:1},"Status, Confidence & Alerts":{min:0,max:32,step:1},"Learning & Metrics":{min:0,max:32,step:1},"Modals & Overlays":{min:0,max:32,step:1}};function Sn(i){let e=parseFloat(String(i||"").trim());return Number.isNaN(e)?null:e}function Ya(i,e){let t=String(e||"").trim();if(!t)return{numeric:null,unit:tt(i)};if(i.type==="number")return{numeric:Sn(t),unit:""};if(i.type==="size"){let r=t.match(/^(-?\d*\.?\d+)\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);return r?{numeric:Number(r[1]),unit:r[2].toLowerCase()}:{numeric:null,unit:tt(i)}}if(i.type==="duration"){let r=t.match(/^(-?\d*\.?\d+)\s*(ms|s)$/i);return r?{numeric:Number(r[1]),unit:r[2].toLowerCase()}:{numeric:null,unit:tt(i)}}return{numeric:null,unit:""}}function tt(i){return i.type==="size"?"px":i.type==="duration"?"ms":""}function Rn(i){return i.type==="size"||i.type==="number"||i.type==="duration"}function En(i,e){return Rn(i)?e==null||e===""?!0:Ya(i,e).numeric!==null:!1}function kn(i){let e=Number(i);return Number.isNaN(e)?100:Math.max(0,Math.min(100,e))}function Tn(i){let e=String(i||"").trim();if(/^#[0-9a-fA-F]{8}$/.test(e)){let t=e.slice(7,9),r=parseInt(t,16)/255;return kn(Math.round(r*100))}return 100}function Qa(i){i.renderThemeView=function(){let e=this.card._state._ensureThemeState(),{tokens:t,sources:r}=this.card._state.resolvedTheme(),a=this.card._state.isMobileViewport(),c=a?"presets":e.activeSubTab||"presets";return`
      <div class="evcc-view evcc-view--theme">
        ${c==="presets"?"":this._renderThemeHeader(e)}

        ${a?"":`
        <div class="evcc-chips evcc-theme-tabs" role="tablist">
          <button
            class="evcc-chip ${c==="presets"?"active":""}"
            data-theme-tab="presets"
          >
            Themes
          </button>

          <button
            class="evcc-chip ${c==="palette"?"active":""}"
            data-theme-tab="palette"
          >
            Palette
          </button>

          <button
            class="evcc-chip ${c==="tokens"?"active":""}"
            data-theme-tab="tokens"
          >
            Tokens
          </button>
        </div>`}

        <div class="evcc-view-content">
          ${c==="presets"?this._renderThemePresets(e):""}
          ${!a&&c==="palette"?this._renderThemePalette(t,r):""}
          ${!a&&c==="tokens"?this._renderThemeTokenEditor(t,r):""}
        </div>

        ${this._renderThemeFooter(e)}
      </div>
    `},i.renderThemeJsonModal=function(e){let{state:t}=e;if(!t.isThemeJsonModalOpen())return"";let r=t.themeJsonModalMode()==="export",a=t.themeJsonModalText();return`
      <div class="evcc-modal-backdrop" data-action="close-theme-json">
        <div class="evcc-modal evcc-modal--theme-json" data-stop-propagation>

          <div class="evcc-modal-header">
            <div class="evcc-modal-title">${r?"Export theme":"Import theme"}</div>
            <button type="button" class="evcc-chip evcc-chip--icon" data-action="close-theme-json" title="Close">\u2715</button>
          </div>

          <div class="evcc-modal-body">
            <p class="evcc-theme-json-hint">${r?"Copy this JSON to share or back up the active theme. It's not saved anywhere \u2014 it's gone when you close this.":"Paste a theme export below, then Import. (Or use Upload for a file.)"}</p>
            <textarea
              class="evcc-theme-json-area"
              data-theme-json-area
              spellcheck="false"
              ${r?"readonly":'placeholder="Paste theme JSON here\u2026"'}
            >${this.escapeHtml(a)}</textarea>
            ${r?"":'<p class="evcc-theme-json-error" data-theme-json-error hidden></p>'}
          </div>

          <div class="evcc-modal-footer">
            <button type="button" class="evcc-chip" data-action="close-theme-json">${r?"Close":"Cancel"}</button>
            ${r?`<button type="button" class="evcc-chip" data-action="notify-theme-json" title="Post this export to a Home Assistant persistent notification to grab later (useful for batch exports when clipboard/download are blocked)">Send to HA</button>
                 <button type="button" class="evcc-chip evcc-chip--save" data-action="copy-theme-json">Copy</button>`:'<button type="button" class="evcc-chip evcc-chip--save" data-action="confirm-theme-import">Import</button>'}
          </div>

        </div>
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
        ${[{value:"all",label:"All"},{value:"modified",label:"Modified"},...ae.map(r=>({value:r,label:r}))].map(r=>`
          <button
            class="evcc-chip ${e===r.value?"active":""}"
            data-theme-group-filter="${this.escapeHtml(r.value)}"
          >
            ${this.escapeHtml(r.label)}
          </button>
        `).join("")}
      </div>
    `},i._renderPresetFilters=function(e){let t=this.card._state.presentPresetTags(),r=Ge.map(o=>{let l=o.tags.filter(d=>t.has(d));return l.length?`
        <div class="evcc-preset-facet">
          <span class="evcc-preset-facet-label">${this.escapeHtml(o.label)}</span>
          ${l.map(d=>`
            <button
              class="evcc-chip evcc-preset-facet-chip ${this.card._state.isPresetFacetActive(o.key,d)?"active":""}"
              data-preset-facet="${this.escapeHtml(o.key)}"
              data-preset-facet-value="${this.escapeHtml(d)}"
            >${this.escapeHtml(d)}</button>
          `).join("")}
        </div>`:""}).filter(Boolean).join(""),a=this.card._state.hasActivePresetFilters(),c=this.card._state.getPresetFiltersOpen(),n=this.card._state.activePresetFacetCount(),s=!!r;return`
      <div class="evcc-preset-filters">
        <div class="evcc-preset-filters-top">
          <div class="evcc-search-box evcc-preset-search">
            <ha-icon icon="mdi:magnify"></ha-icon>
            <input
              type="text"
              placeholder="Search themes..."
              value="${this.escapeHtml(e.presetSearchQuery||"")}"
              data-preset-search
            />
          </div>
          ${s?`
            <button
              class="evcc-chip evcc-preset-filters-toggle ${c?"active":""}"
              data-preset-filters-toggle
              aria-expanded="${c?"true":"false"}"
            >
              <ha-icon icon="mdi:filter-variant"></ha-icon>
              Filters${n?` (${n})`:""}
              <ha-icon class="evcc-preset-filters-caret" icon="mdi:chevron-down"></ha-icon>
            </button>
          `:""}
          ${a?`
            <button class="evcc-chip evcc-preset-clear" data-preset-clear>Clear</button>
          `:""}
          <a
            class="evcc-preset-gallery-link"
            href="${yn}"
            target="_blank"
            rel="noopener noreferrer"
            title="Browse the theme gallery (opens in a new tab)"
          >
            Browse gallery <ha-icon icon="mdi:open-in-new"></ha-icon>
          </a>
        </div>
        ${s&&c?`<div class="evcc-preset-facets">${r}</div>`:""}
      </div>
      <datalist id="evcc-vibe-suggest">
        ${yt.map(o=>`<option value="${this.escapeHtml(o)}"></option>`).join("")}
      </datalist>
    `},i._renderThemePresets=function(e){let t=e.library||{};if(Object.keys(t).length===0)return'<div class="evcc-empty">No themes available.</div>';let a=this.card._state.filteredPresetIds(),c=a.length===0?'<div class="evcc-empty">No themes match these filters.</div>':`
        <div class="evcc-preset-grid">
          ${(()=>{let n=this.card._state.effectiveActiveThemeId();return a.map(s=>{let o=t[s],l=n===s,d=[...Object.entries(o.tokens||{}),...Object.entries(o.colors||{}),...Object.entries(o.alpha||{})].map(([h,b])=>`${h}:${b}`).join(";"),u=this.card._state.presetTagsFor(s),m=xt(u).filter(h=>["mode","accent","a11y","cvd","source"].includes(Xe(h))),p=m.length?`<div class="evcc-preset-tags">${m.map(h=>`<span class="evcc-preset-tag" data-facet="${Xe(h)}">${this.escapeHtml(h)}</span>`).join("")}</div>`:"",v=this.card._state.getPresetTagEditId()===s,f=v?`<div class="evcc-preset-tag-editor" data-preset-tag-editor>
                  <div class="evcc-preset-vibe-chips">
                    ${this.card._state.presetVibeTags(s).map(h=>`
                      <span class="evcc-preset-vibe-chip">${this.escapeHtml(h)}<button
                        class="evcc-preset-vibe-remove"
                        data-preset-tag-remove="${this.escapeHtml(s)}"
                        data-tag="${this.escapeHtml(h)}"
                        title="Remove tag">\xD7</button></span>`).join("")}
                  </div>
                  <div class="evcc-preset-tag-add">
                    <input
                      class="evcc-preset-tag-input"
                      type="text"
                      list="evcc-vibe-suggest"
                      placeholder="add a tag\u2026"
                      maxlength="32"
                      data-preset-tag-add="${this.escapeHtml(s)}"
                    >
                    <button class="evcc-preset-tag-done" data-preset-tag-done title="Done editing tags">
                      <ha-icon icon="mdi:check"></ha-icon>
                    </button>
                  </div>
                </div>`:"";return`
              <div
                class="evcc-preset-card ${l?"active":""} ${v?"editing":""}"
                data-theme-preset="${this.escapeHtml(s)}"
              >
                <button
                  class="evcc-preset-tag-edit ${v?"active":""}"
                  data-preset-tag-edit="${this.escapeHtml(s)}"
                  title="Edit tags"
                >
                  <ha-icon icon="mdi:tag-multiple-outline"></ha-icon>
                </button>
                ${s!==e.defaultThemeId?`
                  <button
                    class="evcc-preset-delete"
                    data-action="delete-preset"
                    data-preset-id="${this.escapeHtml(s)}"
                  >
                    <ha-icon icon="mdi:close-circle"></ha-icon>
                  </button>
                `:""}

                <div class="evcc-preset-preview" style="${d}">
                  <div class="preview-swatch accent"></div>
                  <div class="preview-swatch surface"></div>
                </div>

                <div class="evcc-preset-label">
                  ${this.escapeHtml(o.name||s)}
                  ${l?'<span class="evcc-chip evcc-chip--active">Active</span>':""}
                </div>
                ${p}
                ${f}
              </div>
            `}).join("")})()}
        </div>`;return`${this._renderThemeModeBar(e)}${this._renderPresetFilters(e)}<div class="evcc-preset-scroll">${c}</div>`},i._renderThemeModeBar=function(e){let t=this.card._state.isDeviceThemeMode(),r=this.card._state.effectiveActiveThemeId(),a=e.library?.[r]?.name||"\u2014";return`
      <div class="evcc-theme-mode">
        <div class="evcc-theme-mode-row">
          <span class="evcc-theme-mode-label">Theme mode</span>
          <button class="evcc-chip ${t?"":"active"}" data-theme-mode="system">Follow system</button>
          <button class="evcc-chip ${t?"active":""}" data-theme-mode="device">This device only</button>
        </div>
        ${t?`
          <div class="evcc-theme-mode-detail">
            <div class="evcc-theme-mode-state">
              <span><span class="k">Active theme</span> ${this.escapeHtml(a)}</span>
              <span><span class="k">Mode</span> this device only</span>
            </div>
            <div class="evcc-theme-mode-actions">
              <button class="evcc-chip" data-action="theme-use-everywhere">Use everywhere</button>
              <button class="evcc-chip" data-action="theme-clear-device">Clear device override</button>
            </div>
            <p class="evcc-theme-mode-note">Theme edits are shared. Only the <em>selected</em> theme is local to this browser.</p>
          </div>
        `:""}
      </div>
    `},i._renderThemePalette=function(e,t){let r=ue.filter(a=>et.has(a.key));return`
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
    `},i._renderThemeTokenEditor=function(e,t){let r=this.card._state.getThemeGroupFilter(),a={},c=new Set;for(let o of ae){let l=o.indexOf(" \u2014 ");if(l===-1)continue;let d=o.slice(0,l);ae.includes(d)&&((a[d]=a[d]??[]).push(o),c.add(o))}let n=(o,l=!1)=>{let d=this.card._state.filteredThemeTokensForGroup(o,ue,{excludeKeys:et}),u=this.card._state.getThemeGroupSearchQuery(o),m=String(u||"").trim().length>0,p=r===o||m,f=(a[o]??[]).map(g=>n(g,!0)).filter(Boolean).join("");if(!d.length&&!p&&!f)return"";let h=this.card._state.themeGroupCounts(o,ue,{excludeKeys:et}),w=this.card._state.shouldForceThemeGroupOpenForSearch(o,ue,{excludeKeys:et})||this.card._state.isThemeGroupOpen(o),S=l?o.slice(o.lastIndexOf(" \u2014 ")+3):o;return`
        <div
          class="evcc-token-group ${w?"is-open":"is-closed"} ${l?"evcc-token-group--child":""}"
          data-theme-group-name="${this.escapeHtml(o)}"
        >
          <div
            class="evcc-token-group-header"
            data-theme-group-toggle="${this.escapeHtml(o)}"
          >
            <div class="group-title">
              ${this.escapeHtml(S)} (${h.modified} / ${h.total})
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
                ${w?"\u25BE":"\u25B8"}
              </span>
            </div>
          </div>

          ${w?`
            <div class="evcc-token-group-body">
              ${d.length?`
                <div class="evcc-token-group-search">
                  <input
                    type="text"
                    placeholder="Search ${this.escapeHtml(S)}..."
                    value="${this.escapeHtml(u)}"
                    data-theme-group-search="${this.escapeHtml(o)}"
                  />
                </div>

                ${d.map(g=>this._renderThemeTokenRow(g,e[g.key],t[g.key])).join("")}

                ${!d.length&&m?`
                  <div class="evcc-empty evcc-empty--theme-group-search">
                    No tokens in ${this.escapeHtml(S)} match "${this.escapeHtml(u)}".
                  </div>
                `:""}
              `:""}

              ${f}
            </div>
          `:""}
        </div>
      `},s=ae.filter(o=>!c.has(o)).map(o=>n(o)).filter(Boolean);return`
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
    `},i._renderThemeTokenRow=function(e,t,r){let a=r==="draft",c=t||"";return e.type==="color"?Ka(c)?this._renderThemeColorMixTokenRow(e,c,a):this._renderThemeColorTokenRow(e,c,a):En(e,c)?this._renderThemeNumericTokenRow(e,c,a):this._renderThemeTextTokenRow(e,c,a)},i._renderThemeColorTokenRow=function(e,t,r){let a=String(t||"").trim(),c=this._safeColorInputValue(a),n=Tn(a),s=/^#[0-9a-fA-F]{8}$/.test(a)?`#${a.slice(1,7)}`:a;return`
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
                  value="${n}"
                  data-theme-alpha="${this.escapeHtml(e.key)}"
                  data-color-swatch="${this.escapeHtml(e.key)}"
                  aria-label="${this.escapeHtml(e.label)} opacity"
                />

                <div
                  class="token-alpha-indicator"
                  data-theme-alpha-indicator="${this.escapeHtml(e.key)}"
                  style="left: ${n}%"
                ></div>
              </div>

              <div
                class="token-slider-bubble token-slider-bubble--alpha"
                data-theme-alpha-bubble="${this.escapeHtml(e.key)}"
                style="left: ${n}%"
              >
                ${n}%
              </div>
            </div>
          </div>

          <input
            type="color"
            class="hidden-color-input"
            value="${c}"
            data-theme-color-input="${this.escapeHtml(e.key)}"
            tabIndex="-1"
          />
        </div>
      </div>
    `},i._renderThemeColorMixTokenRow=function(e,t,r){let a=Ka(t);if(!a)return this._renderThemeColorTokenRow(e,t,r);let{color1:c,ratio:n,color2:s}=a,o=this.escapeHtml(xn(c,n,s));return`
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
            <div class="token-colormix-swatch" style="background: ${this.escapeHtml(c)}"></div>
            <input
              type="text"
              class="token-input token-colormix-color"
              data-theme-colormix="${this.escapeHtml(e.key)}"
              data-colormix-part="color1"
              value="${this.escapeHtml(c)}"
              spellcheck="false"
              autocapitalize="off"
            />
          </div>

          <div class="token-colormix-ratio-label" data-colormix-ratio-label="${this.escapeHtml(e.key)}">
            ${n}%
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
            value="${n}"
            data-theme-colormix="${this.escapeHtml(e.key)}"
            data-colormix-part="ratio"
          />
        </div>

        <div
          class="token-colormix-preview"
          style="background: ${o}"
        ></div>
      </div>
    `},i._renderThemeNumericTokenRow=function(e,t,r){let a=wn[e.group]||{min:0,max:64,step:1},c={min:Number.isFinite(e.min)?e.min:a.min,max:Number.isFinite(e.max)?e.max:a.max,step:Number.isFinite(e.step)?e.step:a.step},n=Ya(e,t),s=n.numeric??c.min,o=n.unit||tt(e),l=e.type==="number"?"":o,d=Math.min(c.min,s),u=Math.max(c.max,s);return`
      <div
        class="evcc-token-row evcc-token-row--numeric ${r?"is-draft":""}"
        data-theme-token-unit="${this.escapeHtml(o)}"
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
              min="${d}"
              max="${u}"
              step="${c.step}"
              value="${s}"
              data-theme-token="${this.escapeHtml(e.key)}"
            />

            <div
              class="token-slider-bubble"
              data-theme-slider-bubble="${this.escapeHtml(e.key)}"
            >
              ${s}${this.escapeHtml(l)}
            </div>
          </div>
        </div>

        <div class="token-control-row token-control-row--number">
          <input
            type="number"
            class="token-input token-input--number"
            min="${d}"
            max="${u}"
            step="${c.step}"
            value="${s}"
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
    `},i._renderThemeFooter=function(e){let t=!!e.draftDirty,r=!!e.activeThemeId,a=this.card._state.isMobileViewport();return`
      <div class="evcc-view-footer">
        <div class="footer-left">
          <button
            class="evcc-chip"
            data-action="export-theme"
            title="Copy theme JSON to clipboard"
          >
            Export
          </button>

          <button
            class="evcc-chip"
            data-action="import-theme"
            title="Paste theme JSON from clipboard"
          >
            Import
          </button>

          <button
            class="evcc-chip"
            data-action="download-theme"
            title="Download theme as a .json file"
          >
            Download
          </button>

          <button
            class="evcc-chip"
            data-action="upload-theme"
            title="Upload a theme .json file"
          >
            Upload
          </button>

          ${a?"":`
          <select
            class="evcc-chip evcc-floor-scope-select"
            data-theme-floor-scope
            title="Floor type to export as a shareable preset"
          >
            ${Et().map(c=>`<option value="${c}">${c}</option>`).join("")}
          </select>

          <button
            class="evcc-chip"
            data-action="download-floor-theme"
            title="Download just this floor type as a shareable preset .json"
          >
            Download Floor
          </button>

          <select
            class="evcc-chip evcc-floor-scope-select"
            data-floor-preset
            title="Built-in marble preset to apply to the active theme"
          >
            ${Ze.map(c=>`<option value="${c.id}">${this.escapeHtml(c.name)}</option>`).join("")}
          </select>

          <button
            class="evcc-chip"
            data-action="apply-floor-preset"
            title="Apply this built-in marble preset to the active theme"
          >
            Apply Preset
          </button>`}
        </div>

        ${a?"":`
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
        </div>`}
      </div>
    `},i._safeColorInputValue=function(e){let t=String(e||"").trim();return/^#[0-9a-fA-F]{6}$/.test(t)?t:/^#[0-9a-fA-F]{8}$/.test(t)?`#${t.slice(1,7)}`:"#000000"}}var $n={"App Shell & Typography":{method:"_renderThemePreviewShellTypography",title:"Shell & Typography Preview",description:"Accent, heading, and body text examples show the shell voice this group controls."},"Cards & Surfaces":{method:"_renderThemePreviewCardsSurfaces",title:"Cards & Surfaces Preview",description:"Shared card, panel, and input surfaces show the base material language for the editor."},"Borders & Shadows":{method:"_renderThemePreviewBordersShadows",title:"Borders & Shadows Preview",description:"Border strength and elevation samples reveal separation, depth, and hover lift."},Chips:{method:"_renderThemePreviewChips",title:"Chip Preview",description:"A compact chip matrix highlights default, active, hover, success, warning, and excluded states."},"Room Cards":{method:"_renderThemePreviewRoomCards",title:"Room Card Preview",description:"Mini room cards expose profile chips, room chips, and room-surface treatment together."},"Floor Textures":{method:"_renderThemePreviewFloorTextures",title:"Floor Texture Preview",description:"Live swatches show each material's overlay on the card surface. Opacity, scale, and tint tokens update in real time."},"Floor Textures \u2014 Tile":{method:"_renderThemePreviewFloorTextureTile",title:"Tile Floor Preview",description:"Base and accent colors control the grout lines and tile face on card and map surfaces."},"Floor Textures \u2014 Wood":{method:"_renderThemePreviewFloorTextureWood",title:"Wood Floor Preview",description:"Base and accent colors control the wood grain, seam lines, and directional depth layers."},"Floor Textures \u2014 Marble":{method:"_renderThemePreviewFloorTextureMarble",title:"Marble Floor Preview",description:"Base color tints the marble texture layer on the card surface."},"Floor Textures \u2014 Concrete":{method:"_renderThemePreviewFloorTextureConcrete",title:"Concrete Floor Preview",description:"Base color tints the concrete texture layer on the card surface."},"Floor Textures \u2014 Carpet Low":{method:"_renderThemePreviewFloorTextureCarpetLow",title:"Carpet Low Pile Preview",description:"Base color tints the low-pile carpet texture layer on the card surface."},"Floor Textures \u2014 Carpet High":{method:"_renderThemePreviewFloorTextureCarpetHigh",title:"Carpet High Pile Preview",description:"Base color tints the high-pile carpet texture layer on the card surface."},"Floor Textures \u2014 Granite":{method:"_renderThemePreviewFloorTextureGranite",title:"Granite Floor Preview",description:"Base color tints the granite texture layer on the card surface."},"Queue & Ordering":{method:"_renderThemePreviewQueueOrdering",title:"Queue & Ordering Preview",description:"Queue strip, order chips, and drag feedback samples show sequencing and reorder states."},"Status, Confidence & Alerts":{method:"_renderThemePreviewStatusAlerts",title:"Status & Alerts Preview",description:"Status dots, confidence badges, and alert surfaces show semantic state color relationships."},"Learning & Metrics":{method:"_renderThemePreviewLearningMetrics",title:"Learning & Metrics Preview",description:"Estimate badges and learning panels preview predictive and analytical surfaces."},[Fe]:{method:"_renderThemePreviewAnimalCompanion",title:"Animal Companion Preview",description:"Every registered animal in standing pose across all five battery-state bands. Eye-color and global palette tokens in this group apply across every animal."},"Modals & Overlays":{method:"_renderThemePreviewModalsOverlays",title:"Modal & Overlay Preview",description:"A modal shell sample isolates overlay surfaces, chips, warning states, and backdrop treatment."},"Shared Foundations":{method:"_renderThemePreviewSharedFoundations",title:"Shared Foundations Preview",description:"A mixed control-surface preview shows spacing, radius, motion, and typography primitives together."}},Mn=["cat","dog","raccoon","parrot","snake"];function An(){try{let i=typeof window<"u"&&window.AnimalSVG?.list?window.AnimalSVG.list():null;if(Array.isArray(i)&&i.length>0)return i}catch{}return Mn}function Cn(i){let e={};for(let t of i){let r=String(t||"").replace(/[^a-z0-9-]/gi,"");if(!r)continue;let a=r.charAt(0).toUpperCase()+r.slice(1);e[De(r)]={method:"_renderThemePreviewAnimal",methodArgs:[r],title:`${a} Preview`,description:`The ${r} across all five battery-state bands. Tokens in this sub-group (prefixed --evcc-animal-${r}-) override the global Animal Companion palette and eye-state colors for just the ${r}.`}}return e}function Xa(){let i=An();return Object.freeze({...$n,...Cn(i)})}var Tt=Xa();typeof document<"u"&&document.addEventListener&&document.addEventListener("animal-svg-registered",()=>{try{Tt=Xa()}catch(i){console.warn("[theme-preview-registry] rebuild failed:",i)}});function Za(i){i._renderThemePreviewPane=function(){let t=this.card._state.currentThemePreviewGroup(),r=Tt[t];if(!r)return"";let a=Array.isArray(r.methodArgs)?r.methodArgs:[],c=typeof this[r.method]=="function"?this[r.method](...a):"";return c?`
      <aside class="evcc-theme-preview-column">
        <section class="evcc-theme-preview-pane">
          <div class="evcc-theme-preview-header">
            <div class="evcc-theme-preview-eyebrow">Contextual Preview</div>
            <div class="evcc-theme-preview-title">
              ${this.escapeHtml(r.title)}
            </div>
            <div class="evcc-theme-preview-description">
              ${this.escapeHtml(r.description)}
            </div>
          </div>

          <div class="evcc-theme-preview-body">
            ${c}
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
    `},i._renderThemePreviewFloorTextures=function(){return`<div class="evcc-theme-preview-ftx-card-grid">${[{key:"tile",name:"Tile"},{key:"wood",name:"Wood"},{key:"marble",name:"Marble"},{key:"concrete",name:"Concrete"},{key:"carpet_low",name:"Carpet Low"},{key:"carpet_high",name:"Carpet High"},{key:"granite_light",name:"Granite"}].map(({key:a,name:c})=>this._renderFloorPreviewCard(a,c)).join("")}</div>`},i._renderFloorPreviewCard=function(t,r){return this.renderRoomCard({id:`preview-ftx-${t}`,name:r??t,floor_type:t,enabled:!0,order:1},null)},i._renderThemePreviewFloorTextureTile=function(){return this._renderFloorPreviewCard("tile","Tile")},i._renderThemePreviewFloorTextureWood=function(){return this._renderFloorPreviewCard("wood","Wood")},i._renderThemePreviewFloorTextureMarble=function(){return this._renderFloorPreviewCard("marble","Marble")},i._renderThemePreviewFloorTextureConcrete=function(){return this._renderFloorPreviewCard("concrete","Concrete")},i._renderThemePreviewFloorTextureCarpetLow=function(){return this._renderFloorPreviewCard("carpet_low","Carpet Low")},i._renderThemePreviewFloorTextureCarpetHigh=function(){return this._renderFloorPreviewCard("carpet_high","Carpet High")},i._renderThemePreviewFloorTextureGranite=function(){return this._renderFloorPreviewCard("granite_light","Granite")},i._renderThemePreviewQueueOrdering=function(){return`
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
    `};let e=[{id:"good",label:"Good",hint:"battery > 50%"},{id:"mid",label:"Mid",hint:"25\u201350%"},{id:"warn",label:"Warn",hint:"15\u201325%"},{id:"low",label:"Low",hint:"\u2264 15%"},{id:"charging",label:"Charging",hint:"pulses"}];i._renderAnimalPreviewGrid=function(t,r){let a=`
      <div class="evcc-theme-preview-animal-row evcc-theme-preview-animal-row--header">
        <div class="evcc-theme-preview-animal-rowlabel"></div>
        ${t.map(n=>`
          <div class="evcc-theme-preview-animal-collabel">${this.escapeHtml(n)}</div>
        `).join("")}
      </div>
    `,c=e.map(({id:n,label:s,hint:o})=>`
      <div class="evcc-theme-preview-animal-row">
        <div class="evcc-theme-preview-animal-rowlabel">
          <span class="evcc-theme-preview-animal-rowlabel-title">${this.escapeHtml(s)}</span>
          <span class="evcc-theme-preview-animal-rowlabel-hint">${this.escapeHtml(o)}</span>
        </div>
        ${t.map(l=>`
          <div class="evcc-theme-preview-animal-cell">
            <animal-svg
              animal="${this.escapeHtml(l)}"
              pose="standing"
              battery-state="${this.escapeHtml(n)}"
              width="${t.length===1?"140":"80"}px"
              height="${t.length===1?"96":"55"}px"></animal-svg>
          </div>
        `).join("")}
      </div>
    `).join("");return`
      <div class="evcc-theme-preview-animal-grid${t.length===1?" evcc-theme-preview-animal-grid--single":""}">
        ${a}
        ${c}
      </div>
      <div class="evcc-theme-preview-animal-note">${r}</div>
    `},i._renderThemePreviewAnimalCompanion=function(){let t=window.AnimalSVG&&window.AnimalSVG.list?window.AnimalSVG.list():["cat","dog","raccoon","parrot","snake"];return this._renderAnimalPreviewGrid(t,`Tokens in this <em>parent</em> group apply across <strong>every</strong>
       animal. The five eye-color tokens (<code>--evcc-animal-eye-*</code>) drive
       the rows; the global palette tokens (<code>--evcc-animal-fur</code>,
       <code>--evcc-animal-pupil</code>, etc.) drive every body. Use the
       per-animal sub-groups below to override for a single animal.`)},i._renderThemePreviewAnimal=function(t){let r=String(t||"").replace(/[^a-z0-9-]/gi,"");if(!r)return"";let a=`Tokens in this sub-group (prefixed <code>--evcc-animal-${r}-\u2026</code>) override the global Animal Companion tokens for just the ${r}. Leave any token unset to inherit the parent value (or the ${r}'s own built-in default if no theme value is set).`;return this._renderAnimalPreviewGrid([r],a)},i._renderThemePreviewSharedFoundations=function(){return`
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
    `}}function In(i){switch(i){case"cleaning":return"alert";case"returning":return"walking";case"paused":return"standing";case"error":return"warning";case"docked":case"idle":return"curled";default:return"curled"}}function ei(i){let e=0,t=0,r=0,a=i.length;for(let c=0,n=a-1;c<a;n=c++){let s=i[n][0]*i[c][1]-i[c][0]*i[n][1];e+=s,t+=(i[n][0]+i[c][0])*s,r+=(i[n][1]+i[c][1])*s}if(e*=.5,Math.abs(e)<1e-10){let c=i.reduce((s,o)=>s+o[0],0),n=i.reduce((s,o)=>s+o[1],0);return[c/a,n/a]}return[t/(6*e),r/(6*e)]}var rt=["#00e5ff","#ff6b35","#a3e635","#e879f9","#fbbf24","#a78bfa","#fb7185","#34d399","#60a5fa","#f472b6","#4ade80","#f97316"],On=[{key:"dark",label:"Dark",hint:"primary \u2014 clearest room colours"},{key:"light",label:"Light",hint:"assist \u2014 wall detection"},{key:"default",label:"Default",hint:"fallback"}];function ti(i){i.renderMapRoomView=function(t){let{state:r,vacuumStatus:a}=t,c=r.mapSegmentsData(),n=r.mapImageUrl();if(!c?.available||!n)return`
        <div class="evcc-map-view">
          <div class="evcc-map-unavailable">
            <p>No map image available.</p>
            <p class="evcc-map-unavailable-hint">${(r.segmentationMode?.()??"cv")==="custom"?"Open Map Configuration to upload this layout's backdrop, then draw + save its rooms.":"Upload and analyze a map image to enable map view."}</p>
          </div>
        </div>
      `;let s=r.mapSegments(),o=r.selectedSegmentIds(),l=r.selectedSegments(),d=r.getRoomsForActiveMap?.()??[],u=s.map(f=>{let h=r.roomIdForSegment(f.segment_id),b=h!=null?d.find(w=>String(w.id)===String(h)):null;return typeof this._resolveSegmentFloorType=="function"?this._resolveSegmentFloorType(b):"default"}),m=r.mapZoom?.()??1,p=r.mapTranslateX?.()??0,v=r.mapTranslateY?.()??0;return`
      <div class="evcc-map-view">
        <div class="evcc-map-container">

          <div class="evcc-map-layers" style="transform:translate(${p}px,${v}px) scale(${m});transform-origin:0 0">
            <img
              class="evcc-map-image"
              src="${this.escapeHtml(n)}"
              alt="Floor plan"
              draggable="false"
            >
            <svg
              class="evcc-map-svg"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              ${typeof this._buildFloorTextureDefs=="function"?this._buildFloorTextureDefs(u):""}
              ${s.map((f,h)=>{let b=r.roomIdForSegment(f.segment_id),w=b!=null?d.find(R=>String(R.id)===String(b)):null,S=w?.name??f.name??f.label??`Segment ${f.segment_id}`,g=w?"Tap to queue \xB7 Double-tap to configure":"Tap to queue";return this._renderMapSegmentPolygon(f,o,h,S,g)}).join("")}
              ${typeof this._renderFloorTexturePolygon=="function"?s.map((f,h)=>this._renderFloorTexturePolygon(f,u[h])).join(""):""}
            </svg>
            ${this._renderMapAnimal(r,a)}
            ${s.map(f=>{let h=f.polygon_pct;if(!Array.isArray(h)||h.length<3)return"";let[b,w]=ei(h),S=Math.min(Math.max(b,5),95),g=Math.min(Math.max(w,6),94),R=r.roomIdForSegment(f.segment_id),T=(R!=null?d.find(z=>String(z.id)===String(R)):null)?.name??f.name??f.label??null;if(!T)return"";let M=l.findIndex(z=>String(z.segment_id)===String(f.segment_id)),J=M>=0;return`<div class="evcc-map-label${J?" evcc-map-label--selected":""}" style="left:${S}%;top:${g}%">
                ${J?`<span class="evcc-map-label-order">${M+1}</span>`:""}
                <span class="evcc-map-label-name">${this.escapeHtml(T)}</span>
              </div>`}).join("")}
          </div>

          <div class="evcc-map-tooltip" aria-hidden="true"></div>

          <!-- Zoom controls. Absolute-positioned over the map. CSS-styled
               as a small floating toolbar; see styles/map.js -->
          <div class="evcc-map-zoom-toolbar" aria-label="Map zoom controls">
            <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                    title="Zoom out" aria-label="Zoom out">\u2212</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                    title="Fit map to screen" aria-label="Fit to screen">\u2922</button>
            <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                    title="Zoom in" aria-label="Zoom in">+</button>
            <span class="evcc-map-zoom-readout"
                  aria-label="Current zoom level">${Math.round(m*100)}%</span>
          </div>

        </div>

      </div>
    `},i._renderMapSegmentPolygon=function(t,r,a,c,n){let s=t.polygon_pct;if(!Array.isArray(s)||s.length<3)return"";let o=r.has(String(t.segment_id)),l=rt[a%rt.length],d=s.map(([u,m])=>`${u},${m}`).join(" ");return`<polygon
      class="evcc-map-polygon${o?" evcc-map-polygon--selected":""}"
      points="${d}"
      style="--seg-color:${l}"
      data-action="toggle-segment"
      data-segment-id="${this.escapeHtml(String(t.segment_id))}"
      data-label="${this.escapeHtml(c??"")}"
      data-hint="${this.escapeHtml(n??"")}"
    />`},i._renderMapAnimal=function(t,r){if(!(t.mapAnimalEnabled?.()??!0))return"";let a=t.mapSegments(),c=t.getRoomsForActiveMap?.()??[],n=null,s=y=>{if(y==null)return null;let T=t.segmentIdForRoom?.(y);return T==null?null:a.find(M=>String(M.segment_id)===String(T))??null},o=r==="docked"||r==="idle";if(o){let y=c.find(T=>T.isDockRoom);n=s(y?.id)}if(!n){let y=t.dashboardJobProgress?.(),T=y?.position_room_id??y?.current_room_id;n=s(T)}if(n||(n=a[0]??null),!n)return"";let l=t.roomIdForSegment(n.segment_id),d=o?"dock":l!=null?String(l):`seg_${n.segment_id}`,u,m,p=t.roomDotAnchor?.(d);if(p)u=p.pct_x,m=p.pct_y;else{let y=n.polygon_pct;if(!Array.isArray(y)||y.length<3)return"";[u,m]=ei(y)}let v=In(r??""),f=v==="curled",h=t.mapAnimalSelection?.()??"cat",b=t.mapAnimalScale?.()??1,w=t.batteryState?.()??"good",S=d,g=Math.round(64*b),R=Math.round(44*b);return`<div
      class="evcc-map-animal${f?" evcc-map-animal--pulse":""}"
      style="left:${u}%;top:${m}%;width:${g}px;height:${R}px"
      data-action="map-dot-click"
      data-anchor-key="${this.escapeHtml(S)}"
      title="${o?"Drag to set the mascot's docked home spot":"Drag to reposition"}"
    ><animal-svg animal="${this.escapeHtml(h)}" pose="${this.escapeHtml(v)}" width="${g}px" height="${R}px" battery-state="${this.escapeHtml(w)}"></animal-svg></div>`},i._renderMapSelectionBar=function(t,r){let a=r.getRoomsForActiveMap?.()??[];return`<div class="evcc-map-selection-bar">${t.map((n,s)=>{let o=r.roomIdForSegment(n.segment_id),l=o!=null?a.find(m=>String(m.id)===String(o)):null,d=l?.name??n.name??n.label??`Segment ${n.segment_id}`,u=l?this._mapRoomSettingsSummary(l):"";return`
        <div
          class="evcc-map-chip"
          data-action="map-chip-activate"
          data-segment-id="${this.escapeHtml(String(n.segment_id))}"
          data-room-id="${o!=null?this.escapeHtml(String(o)):""}"
        >
          <span class="evcc-map-chip-order">${s+1}</span>
          <div class="evcc-map-chip-body">
            <span class="evcc-map-chip-label">${this.escapeHtml(d)}</span>
            ${u?`<span class="evcc-map-chip-settings">${this.escapeHtml(u)}</span>`:""}
          </div>
        </div>
      `}).join("")}</div>`},i._mapRoomSettingsSummary=function(t){let r=[];return t.fanSpeed&&r.push(t.fanSpeed),t.waterLevel&&r.push(t.waterLevel),r.join(" \xB7 ")},i.renderMapConfigView=function(t){let{state:r}=t,a=r.mapSegmentsData(),c=r.mapImageUrl(),n=r.mapSegments(),s=r.configSelectedSegmentId(),o=r.configSelectedSegment(),l=a?.image_variants??{},d={...a?.summary??{},analyzed_at:a?.analyzed_at},u=r.mapActionStatus?.()??null,m=(r.segmentationMode?.()??"cv")==="custom",p=r.mapZoom?.()??1,v=r.mapTranslateX?.()??0,f=r.mapTranslateY?.()??0;return`
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
            ${c?`<div class="evcc-map-layers" style="transform:translate(${v}px,${f}px) scale(${p});transform-origin:0 0">
                   <img class="evcc-map-image${m?" evcc-map-image--fill":""}" src="${this.escapeHtml(c)}" alt="Floor plan" draggable="false">
                   <svg class="evcc-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                     ${m?this._renderComposerShapes(r):n.map((h,b)=>{let w=String(h.segment_id)===String(s??"");return this._renderConfigPolygon(h,s,b,w?r.configSelectedVertexIndex?.()??null:null,p)}).join("")}
                   </svg>
                 </div>
                 <div class="evcc-map-zoom-toolbar" aria-label="Map zoom controls">
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-out"
                           title="Zoom out" aria-label="Zoom out">\u2212</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-fit"
                           title="Fit map to screen" aria-label="Fit to screen">\u2922</button>
                   <button class="evcc-map-zoom-btn" data-action="map-zoom-in"
                           title="Zoom in" aria-label="Zoom in">+</button>
                   <span class="evcc-map-zoom-readout"
                         aria-label="Current zoom level">${Math.round(p*100)}%</span>
                 </div>`:`<div class="evcc-map-unavailable">
                   <p>No map image uploaded yet.</p>
                 </div>`}
          </div>

          <div class="evcc-map-config-side-panel">
            ${m?this._renderComposerToolbar(r):o?this._renderSegmentAdjustSection(o,r):`<div class="evcc-map-config-section evcc-map-config-section--hint">
                     <p>Click a segment on the map to adjust it.</p>
                   </div>`}
          </div>

        </div>

        <div class="evcc-map-config-panel">
          ${this._renderSegmentationToggle(r)}
          ${(r.segmentationMode?.()??"cv")==="custom"?this._renderCustomBackdropSection(l,u,r):this._renderVariantsSection(l,d,u,r)}
        </div>

      </div>
    `},i._renderConfigPolygon=function(t,r,a,c,n=1){let s=t.polygon_pct;if(!Array.isArray(s)||s.length<3)return"";let o=String(t.segment_id)===String(r??""),l=rt[a%rt.length],d=s.map(([v,f])=>`${v},${f}`).join(" "),u=this.escapeHtml(String(t.segment_id)),m=`<polygon
      class="evcc-map-polygon evcc-map-polygon--config"
      points="${d}"
      style="fill:${l};fill-opacity:${o?"0.20":"0.06"};stroke:${o?"#ffffff":l};stroke-width:${o?"1.8":"1.1"};stroke-opacity:${o?"1":"0.7"};vector-effect:non-scaling-stroke"
      data-action="config-select-segment"
      data-segment-id="${u}"
    />`,p="";return o&&(p=s.map(([v,f],h)=>{let b=c===h;return`<circle
          class="evcc-map-vertex-dot${b?" evcc-map-vertex-dot--selected":""}"
          cx="${v}" cy="${f}" r="${((b?1.1:.65)/n).toFixed(3)}"
          style="fill:${b?"#ffdd00":l};stroke:${b?"#000":"rgba(0,0,0,0.55)"};stroke-width:0.9;pointer-events:all;cursor:pointer;vector-effect:non-scaling-stroke"
          data-action="select-vertex"
          data-segment-id="${u}"
          data-vertex-index="${h}"
        />`}).join("")),`<g>${m}${p}</g>`};function e(t){if(!t)return null;let r=new Date(t);if(isNaN(r))return null;let a=Date.now()-r.getTime(),c=Math.floor(a/6e4);if(c<1)return"just now";if(c<60)return`${c}m ago`;let n=Math.floor(c/60);if(n<24)return`${n}h ago`;let s=Math.floor(n/24);return s<14?`${s}d ago`:r.toLocaleDateString(void 0,{month:"short",day:"numeric"})}i._renderSegmentationToggle=function(t){let r=t.segmentationMode?.()??"cv",a=t.customLayouts?.()??[],c=t.activeCustomLayoutId?.(),n=t.isLayoutEditorOpen?.(),s=t.layoutEditorMode?.()??"new",o=t.layoutDraftName?.()??"",l=p=>this.escapeHtml(String(p)),d=`
      <button class="evcc-map-mode-btn${r==="cv"?" evcc-map-mode-btn--active":""}"
        data-action="set-segmentation-mode" data-mode="cv"
        title="Detect rooms automatically from the map image">Auto (CV)</button>`,u=a.map(p=>`
      <button class="evcc-map-mode-btn${r==="custom"&&String(p.id)===String(c)?" evcc-map-mode-btn--active":""}"
        data-action="set-active-custom-layout" data-layout-id="${l(p.id)}"
        title="Custom layout: ${l(p.name)}">${l(p.name)}</button>`).join("");return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Segmentation</div>
        <div class="evcc-map-mode-toggle">
          ${d}${u}
      <button class="evcc-map-mode-btn" data-action="open-new-layout"
        title="Add a custom layout (its own backdrop + rooms)">\uFF0B New</button>
        </div>
        ${n?`
        <div class="evcc-compose-tools">
          <input type="text" class="evcc-map-config-input" data-layout-field="name"
            value="${l(o)}" placeholder="Layout name" />
          <button class="evcc-map-config-btn evcc-map-config-btn--primary"
            data-action="${s==="rename"?"rename-layout-save":"create-layout-save"}"
          >${s==="rename"?"Save":"Create"}</button>
          <button class="evcc-map-config-btn" data-action="cancel-layout-editor">Cancel</button>
        </div>`:""}
        ${r==="custom"&&c?`
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="open-rename-layout">Rename</button>
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="delete-layout">Delete layout</button>
        </div>`:""}
      </div>
    `},i._renderCustomBackdropSection=function(t,r,a){let c=a?.activeCustomLayout?.()?.backdrop_variant||"custom",n=t?.[c],s=r?.type==="upload"&&r?.variant===c&&r?.status==="busy",o=r?.type==="upload"&&r?.variant===c&&r?.status==="error",l=n?`${n.width} \xD7 ${n.height}`:"no backdrop yet";return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Custom backdrop</div>
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">Backdrop image</span>
            <span class="evcc-map-variant-hint">any map picture \u2014 drawn on, never auto-segmented</span>
          </div>
          <span class="evcc-map-variant-status ${n?"evcc-map-variant-status--ok":"evcc-map-variant-status--missing"}">${l}</span>
          ${o?`<span class="evcc-map-action-status evcc-map-action-status--error">${this.escapeHtml(r.message??"Upload failed")}</span>`:""}
          <button
            class="evcc-map-config-btn${s?" evcc-map-config-btn--busy":""}"
            data-action="upload-map-variant"
            data-variant="${this.escapeHtml(c)}"
            ${s?"disabled":""}
          >${s?"Uploading\u2026":n?"Replace":"Upload"}</button>
        </div>
      </div>
    `},i._renderComposerShapes=function(t){let r=t.composeDraft?.()??[],a=t.composeSelectedId?.(),c=d=>d.group??d.id,n={};for(let d of r)n[c(d)]=(n[c(d)]||0)+1;let s=["#5ac8fa","#ffd60a","#ff9f0a","#bf5af2","#30d158","#ff6482"],o={},l=0;for(let d of r){let u=c(d);n[u]>=2&&!(u in o)&&(o[u]=s[l++%s.length])}return r.map(d=>this._renderComposerShape(d,d.id===a,o[c(d)]??null)).join("")},i._renderComposerShape=function(t,r,a){let c="evcc-compose-shape";r&&(c+=" evcc-compose-shape--selected"),t.op==="subtract"&&(c+=" evcc-compose-shape--cut");let n=a?` style="--evcc-grp:${a}"`:"",s,o,l="";t.type==="circle"?(s="ellipse",o=`cx="${t.cx}" cy="${t.cy}" rx="${t.r}" ry="${t.r}"`):t.type==="polygon"?(s="polygon",o=`points="${(t.points||[]).map(([m,p])=>`${m},${p}`).join(" ")}"`):(s="rect",o=`x="${t.x}" y="${t.y}" width="${t.w}" height="${t.h}"`,t.angle&&(l=` transform="rotate(${t.angle} ${t.x+t.w/2} ${t.y+t.h/2})"`));let d=r?`<${s} class="evcc-compose-shape-halo"${l} ${o}/>`:"",u=`<${s} class="${c}"${n}${l} data-action="compose-select" data-shape-id="${this.escapeHtml(String(t.id))}" ${o}/>`;return d+u},i._renderComposerToolbar=function(t){let r=t.composeDraft?.().length??0,a=t.composeSelectedId?.()!=null,c=t.mapActionStatus?.()??null,n=c?.type==="compose-save"&&c?.status==="busy",s=c?.type==="compose-save"&&c?.status==="error";return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Compose rooms</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="rect">\uFF0B Rectangle</button>
          <button class="evcc-map-config-btn" data-action="compose-add" data-shape-type="circle">\uFF0B Circle</button>
        </div>
        <div class="evcc-map-config-adj-meta">${r} shape${r===1?"":"s"}${a?"":r?" \xB7 tap one to edit":" \xB7 add a shape to start"}</div>
      </div>
      ${this._renderComposerSelectedControls(t)}
      ${this._renderComposerRoomAssign(t)}
      <div class="evcc-map-config-section">
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn evcc-map-config-btn--danger" data-action="compose-delete" ${a?"":"disabled"}>Delete</button>
          <button class="evcc-map-config-btn" data-action="compose-clear" ${r?"":"disabled"}>Clear all</button>
        </div>
        <button
          class="evcc-map-config-btn evcc-map-config-btn--primary${n?" evcc-map-config-btn--busy":""}"
          data-action="compose-save"
          ${r&&!n?"":"disabled"}
        >${n?"Saving\u2026":"Save rooms"}</button>
        ${s?`<span class="evcc-map-action-status evcc-map-action-status--error">${this.escapeHtml(c.message??"Save failed")}</span>`:""}
      </div>
    `},i._renderComposerSelectedControls=function(t){let r=t.composeSelectedId?.();if(r==null)return"";let a=t.composeDraft?.()??[],c=a.find(v=>v.id===r);if(!c)return"";let n=c.group??c.id,s=a.filter(v=>(v.group??v.id)===n).length,o=t.composeMergeFrom?.()===c.id,l=a.length,d=t.composeMoveScope?.()??"room",u=t.composeStep?.()??3,m=(v,f,h,b)=>`
      <button class="evcc-map-nudge-btn" data-action="compose-move"
        data-dx="${v}" data-dy="${f}" title="${b}">${h}</button>`,p=(v,f)=>`
      <button class="evcc-map-config-btn${u===v?" evcc-map-config-btn--primary":""}"
        data-action="compose-step" data-step="${v}">${f}</button>`;return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Selected: <em>${c.type}</em></div>
        <div class="evcc-compose-tools">
          ${p(1,"Fine")}${p(3,"Med")}${p(7,"Coarse")}
        </div>
        ${s>=2?`
        <div class="evcc-map-config-adj-meta">Move: the whole room, or just this piece</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${d==="room"?" evcc-map-config-btn--primary":""}"
            data-action="compose-move-scope" data-scope="room" title="Move the whole room together">Room</button>
          <button class="evcc-map-config-btn${d==="piece"?" evcc-map-config-btn--primary":""}"
            data-action="compose-move-scope" data-scope="piece" title="Move just this shape">Piece</button>
        </div>`:""}
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">${m(0,-1,"\u2191","Up")}</div>
          <div class="evcc-map-nudge-row">${m(-1,0,"\u2190","Left")}${m(1,0,"\u2192","Right")}</div>
          <div class="evcc-map-nudge-row">${m(0,1,"\u2193","Down")}</div>
        </div>
        <div class="evcc-map-config-adj-meta">\u2026or tap the map to drop the shape there.</div>
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="0.85" title="Shrink">\uFF0D Scale</button>
          <button class="evcc-map-config-btn" data-action="compose-scale" data-factor="1.18" title="Grow">\uFF0B Scale</button>
        </div>
        ${c.type==="rect"?`
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="-1">\uFF0D W</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="w" data-delta="1">\uFF0B W</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="-1">\uFF0D H</button>
          <button class="evcc-map-config-btn" data-action="compose-resize" data-dim="h" data-delta="1">\uFF0B H</button>
        </div>`:""}
        ${c.type!=="circle"?`
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="-15" title="Rotate left">\u21BA Rotate</button>
          <button class="evcc-map-config-btn" data-action="compose-rotate" data-deg="15" title="Rotate right">\u21BB Rotate</button>
        </div>`:""}
        <div class="evcc-compose-tools">
          ${o?'<button class="evcc-map-config-btn evcc-map-config-btn--primary" data-action="compose-merge-cancel" title="Stop merging">Cancel \u2014 tap a shape to merge</button>':`<button class="evcc-map-config-btn" data-action="compose-merge-start" ${l<2?"disabled":""} title="Combine another shape into this room">\u26D3 Merge</button>`}
          ${s>=2?'<button class="evcc-map-config-btn" data-action="compose-split" title="Make this shape its own room again">Split out</button>':""}
        </div>
        ${s>=2?`
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn${c.op==="subtract"?" evcc-map-config-btn--primary":""}"
            data-action="compose-toggle-op"
            title="${c.op==="subtract"?"Carving a hole \u2014 tap to fill instead":"Carve this shape out of the room (cutout)"}"
          >${c.op==="subtract"?"\u26CF Cutout (carving)":"Make cutout"}</button>
        </div>`:""}
        <div class="evcc-compose-tools">
          <button class="evcc-map-config-btn" data-action="compose-deselect" title="Stop editing this shape">Done</button>
        </div>
      </div>
    `},i._renderComposerRoomAssign=function(t){let r=t.composeSelectedId?.();if(r==null)return"";let a=t.composeDraft?.()??[],c=a.find(d=>d.id===r);if(!c)return"";let n=t.getRoomsForActiveMap?.()??[];if(!n.length)return`
        <div class="evcc-map-config-section evcc-map-config-section--hint">
          <p>No rooms discovered for this map yet \u2014 link a shape to a room here once they appear.</p>
        </div>`;let s=d=>d.group??d.id,o=s(c);return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Link to room</div>
        <div class="evcc-map-room-assign-chips">${n.map(d=>{let u=c.room_id!=null&&String(d.id)===String(c.room_id),m=!u&&a.some(v=>s(v)!==o&&v.room_id!=null&&String(v.room_id)===String(d.id)),p="evcc-map-room-assign-chip";return u&&(p+=" evcc-map-room-assign-chip--linked"),m&&(p+=" evcc-map-room-assign-chip--taken"),`
        <button class="${p}" data-action="compose-assign-room"
          data-shape-id="${this.escapeHtml(String(c.id))}"
          data-room-id="${this.escapeHtml(String(d.id))}"
          ${m?"disabled":""}
          title="${m?"Already linked to another shape":u?"Unlink":"Link to "+this.escapeHtml(d.name)}"
        >${this.escapeHtml(d.name)}${u?" \u2713":""}</button>`}).join("")}</div>
      </div>`},i._renderVariantsSection=function(t,r,a,c){let n=c?.mapVariantDeleteArmed?.()??null,s=On.map(({key:p,label:v,hint:f})=>{let h=t[p],b=a?.type==="upload"&&a?.variant===p&&a?.status==="busy",w=a?.type==="analyze"&&a?.variant===p&&a?.status==="busy",S=b||w,g=a?.type==="upload"&&a?.variant===p&&a?.status==="error",R=h?`${h.width} \xD7 ${h.height}`:"not uploaded",y=h?"evcc-map-variant-status--ok":"evcc-map-variant-status--missing",T=b?"Uploading\u2026":w?"Analyzing\u2026 (10-30s)":"Upload";return`
        <div class="evcc-map-variant-row">
          <div class="evcc-map-variant-info">
            <span class="evcc-map-variant-label">${this.escapeHtml(v)}</span>
            <span class="evcc-map-variant-hint">${this.escapeHtml(f)}</span>
          </div>
          <span class="evcc-map-variant-status ${y}">${R}</span>
          ${g?`<span class="evcc-map-action-status evcc-map-action-status--error">
                 ${this.escapeHtml(a.message??"Upload failed")}
               </span>`:""}
          <button
            class="evcc-map-config-btn${S?" evcc-map-config-btn--busy":""}"
            data-action="upload-map-variant"
            data-variant="${p}"
            ${S?"disabled":""}
          >${T}</button>
          ${h?(()=>{let M=n===p,J=a?.type==="delete"&&a?.variant===p&&a?.status==="busy",z=J?"Deleting\u2026":M?"Confirm Delete":"Delete";return`
              <button
                class="${"evcc-map-config-btn evcc-map-config-btn--danger"+(M?" evcc-map-config-btn--confirm":"")+(J?" evcc-map-config-btn--busy":"")}"
                data-action="delete-map-variant"
                data-variant="${p}"
                title="${M?"Click again to confirm \u2014 or click anywhere else to cancel":"Delete this image (does not affect the map itself)"}"
                ${J?"disabled":""}
              >${z}</button>
              ${M?`
                <button
                  class="evcc-map-config-btn"
                  data-action="cancel-delete-map-variant"
                  title="Cancel the pending delete"
                >Cancel</button>
              `:""}
            `})():""}
          <!-- File input is created in-memory by the click binding (bindings/map.js).
               Keeping it out of the DOM avoids re-render orphan issues when HA pushes
               state updates between picker open and file selection. -->
        </div>
      `}).join(""),o=r.segment_count??r.count??0,l=r.adjusted_count??0,d=a?.type==="analyze"&&a?.status==="busy",u=a?.type==="analyze"&&a?.status==="error",m=e(r.analyzed_at);return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Image Variants</div>
        ${s}
        <div class="evcc-map-config-analyze-row">
          <span class="evcc-map-config-seg-count">
            ${u?`<span class="evcc-map-action-status evcc-map-action-status--error">
                   ${this.escapeHtml(a.message??"Analysis failed")}
                 </span>`:o>0?`${o} segments${l>0?`, ${l} adjusted`:""}${m?` \xB7 ${m}`:""}`:"No segments analysed"}
          </span>
          <button
            class="evcc-map-config-btn evcc-map-config-btn--primary${d?" evcc-map-config-btn--busy":""}"
            data-action="analyze-map"
            ${d?"disabled":""}
          >${d?"Analysing\u2026":o>0?"Re-analyse":"Analyse map"}</button>
        </div>
      </div>
    `},i._renderSegmentAdjustSection=function(t,r){let a=t.name??t.label??`Segment ${t.segment_id}`,c=this.escapeHtml(String(t.segment_id));return`
      ${this._renderTranslationSection(t,r,c,a)}
      ${this._renderEdgeSection(t,r,c)}
      ${this._renderVertexSection(t,r,c)}
      ${this._renderRoomAssignSection(t,r)}
    `},i._renderTranslationSection=function(t,r,a,c){let n=r.mapNudgeStep(),s=t.translation_offset,o=Array.isArray(s)?s[0]??0:s?.x??0,l=Array.isArray(s)?s[1]??0:s?.y??0;return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">
          Adjusting: <em>${this.escapeHtml(c)}</em>
        </div>
        <div class="evcc-map-config-adj-meta">Offset: ${o} px, ${l} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${a}" data-dx="0" data-dy="-${n.y}" title="Nudge up">\u2191</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${a}" data-dx="-${n.x}" data-dy="0" title="Nudge left">\u2190</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-segment-adjustment"
              data-segment-id="${a}" title="Reset translation">\u25CB</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${a}" data-dx="${n.x}" data-dy="0" title="Nudge right">\u2192</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-segment"
              data-segment-id="${a}" data-dx="0" data-dy="${n.y}" title="Nudge down">\u2193</button>
          </div>
        </div>
      </div>
    `},i._renderEdgeSection=function(t,r,a){let c=r.mapNudgeStep(),n=t.edge_adjustment??{};return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Edges</div>
        <div class="evcc-map-edge-grid">${[{key:"top",label:"Top",stepKey:"y"},{key:"bottom",label:"Bottom",stepKey:"y"},{key:"left",label:"Left",stepKey:"x"},{key:"right",label:"Right",stepKey:"x"}].map(({key:l,label:d,stepKey:u})=>{let m=n[l]??0,p=c[u];return`
        <div class="evcc-map-edge-row">
          <span class="evcc-map-edge-label">${d}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${a}"
            data-edge="${l}" data-delta="-${p}" title="Contract ${d}">\u2212</button>
          <span class="evcc-map-edge-val">${m>0?"+":""}${m}</span>
          <button class="evcc-map-nudge-btn evcc-map-nudge-btn--edge"
            data-action="adjust-edge" data-segment-id="${a}"
            data-edge="${l}" data-delta="${p}" title="Expand ${d}">+</button>
        </div>
      `}).join("")}</div>
      </div>
    `},i._renderVertexSection=function(t,r,a){let c=t.polygon_pct??t.polygon_pixel??[],n=t.vertex_adjustment??[],s=r.configSelectedVertexIndex?.(),o=r.mapNudgeStep();if(c.length===0)return"";let l={};n.forEach(m=>{l[m.index]=m});let d=c.map((m,p)=>{let v=s===p,f=l[p]!=null,h="evcc-map-vertex-chip";return v&&(h+=" evcc-map-vertex-chip--selected"),f&&(h+=" evcc-map-vertex-chip--adjusted"),`<button class="${h}" data-action="select-vertex"
        data-segment-id="${a}" data-vertex-index="${p}">${p}</button>`}).join(""),u="";if(s!=null&&s<c.length){let m=l[s],p=m?.delta_x??0,v=m?.delta_y??0;u=`
        <div class="evcc-map-config-adj-meta">V${s}: ${p>=0?"+":""}${p}, ${v>=0?"+":""}${v} px</div>
        <div class="evcc-map-nudge-pad">
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${a}" data-vertex-index="${s}"
              data-dx="0" data-dy="-${o.y}" title="Nudge vertex up">\u2191</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${a}" data-vertex-index="${s}"
              data-dx="-${o.x}" data-dy="0" title="Nudge vertex left">\u2190</button>
            <button class="evcc-map-nudge-btn evcc-map-nudge-btn--reset"
              data-action="reset-vertex"
              data-segment-id="${a}" data-vertex-index="${s}"
              title="Reset this vertex">\u25CB</button>
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${a}" data-vertex-index="${s}"
              data-dx="${o.x}" data-dy="0" title="Nudge vertex right">\u2192</button>
          </div>
          <div class="evcc-map-nudge-row">
            <button class="evcc-map-nudge-btn" data-action="nudge-vertex"
              data-segment-id="${a}" data-vertex-index="${s}"
              data-dx="0" data-dy="${o.y}" title="Nudge vertex down">\u2193</button>
          </div>
        </div>
      `}return`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Vertices</div>
        <div class="evcc-map-vertex-chips">${d}</div>
        ${u}
      </div>
    `},i._renderRoomAssignSection=function(t,r){let a=r.getRoomsForActiveMap?.()??[],c=r.roomIdForSegment(t.segment_id),n=this.escapeHtml(String(t.segment_id));return a.length===0?"":`
      <div class="evcc-map-config-section">
        <div class="evcc-map-config-section-title">Link to room</div>
        <div class="evcc-map-room-assign-chips">${a.map(o=>{let l=c!=null&&String(o.id)===String(c),d=!l&&r.segmentIdForRoom(o.id)!=null,u="evcc-map-room-assign-chip";return l&&(u+=" evcc-map-room-assign-chip--linked"),d&&(u+=" evcc-map-room-assign-chip--taken"),`
        <button
          class="${u}"
          data-action="assign-segment-room"
          data-segment-id="${n}"
          data-room-id="${this.escapeHtml(String(o.id))}"
          ${d?"disabled":""}
          title="${d?"Already linked to another segment":l?`Unlink ${this.escapeHtml(o.name)}`:`Link to ${this.escapeHtml(o.name)}`}"
        >${this.escapeHtml(o.name)}${l?" \u2713":""}</button>
      `}).join("")}</div>
      </div>
    `}}function $t(i){let e=String(i?.floor_type??"").toLowerCase().trim(),t=String(i?.carpet_type??"").toLowerCase().trim();return e==="carpet"?t==="high_pile"||t==="high"?"carpet_high":"carpet_low":e==="carpet_low_pile"||e==="carpet_low"?"carpet_low":e==="carpet_high_pile"||e==="carpet_high"?"carpet_high":e==="hardwood"||e==="laminate"||e==="wood"?"wood":e==="tile"?"tile":e==="marble"?"marble":e==="concrete"?"concrete":e==="granite"||e==="granite_light"?"granite_light":"default"}function Ln(i){let e=String(i??""),t=2166136261;for(let c=0;c<e.length;c++)t^=e.charCodeAt(c),t=Math.imul(t,16777619)>>>0;let r=t%101,a=(t>>>13^t>>>7)%101;return`${r}% ${a}%`}function ri(i){i._resolveSegmentFloorType=function(e){return $t({floor_type:e?.floor_type??e?.floorType??"",carpet_type:e?.carpet_type??e?.carpetType??""})},i._renderFloorTextureLayer=function(e){if(!(this.card?._state?.roomFloorTextureEnabled?.()??!0))return"";let t=$t({floor_type:e?.floorType??"",carpet_type:e?.carpetType??""}),r=Oe[t]??Oe.default,a=r.opacityDefault??.85,c=`var(--evcc-floor-${t}-opacity-card,var(--evcc-floor-texture-opacity-card,${a}))`,n=Ln(e?.id??e?.name??t),s=r.layers.map(o=>{let l=`var(${o.colorToken},${o.colorDefault})`,d=`url(${o.url})`,u=`var(${o.opacityToken},${o.opacityDefault})`,m=`<span class="evcc-ftx-layer" data-role="${o.role}" style="background-color:${l};mask-image:${d};-webkit-mask-image:${d};mask-mode:luminance;-webkit-mask-source-type:luminance;--layer-opacity:${u}"></span>`;if(!o.blurToken&&!o.blurDefault)return m;let p=`var(${o.blurToken},${o.blurDefault??"0px"})`;return`<span class="evcc-ftx-blur" style="filter:blur(${p});-webkit-filter:blur(${p})">${m}</span>`}).join("");return`<div class="evcc-room-texture-layer" data-floor="${t}" style="--floor-opacity-card:${c};--floor-position-card:${n}">${s}</div>`},i._buildFloorTextureDefs=function(e){if(!(this.card?._state?.mapFloorTextureEnabled?.()??!0))return"";let t=new Set,r=[];for(let a of e){if(t.has(a))continue;t.add(a);let c=St(a);c&&r.push(`<pattern id="evcc-ftx-${a}" patternUnits="userSpaceOnUse" width="8" height="8"><image href="${c}" width="8" height="8" preserveAspectRatio="xMidYMid slice"/></pattern>`)}return r.length?`<defs>${r.join("")}</defs>`:""},i._renderFloorTexturePolygon=function(e,t){if(!(this.card?._state?.mapFloorTextureEnabled?.()??!0))return"";let r=e.polygon_pct;return!Array.isArray(r)||r.length<3||!St(t)?"":`<polygon class="evcc-map-texture-polygon" points="${r.map(([c,n])=>`${c},${n}`).join(" ")}" fill="url(#evcc-ftx-${t})" data-floor="${t}"/>`}}var Pn=[{value:"hardwood",label:"Hardwood"},{value:"laminate",label:"Laminate"},{value:"tile",label:"Tile"},{value:"marble",label:"Marble"},{value:"granite",label:"Granite"},{value:"concrete",label:"Concrete"},{value:"carpet_low_pile",label:"Low-Pile Carpet"},{value:"carpet_high_pile",label:"High-Pile Carpet"}];function ii(i){i.renderSetupView=function(e){let{state:t,card:r}=e,a=r._config?.vacuum_entity_id??"",c=t.setupStatus?.()??null,n=t.setupLoading?.()??!1,s=t.setupError?.()??null,o=t.setupLastResult?.()??null,l=Array.isArray(c?.vacuums)?c.vacuums:[],d=l.find(k=>k.vacuum_entity_id===a)??null,u=Array.isArray(d?.setup_steps)&&d.setup_steps.length?d.setup_steps:Nn(d),m=d?.room_drift??null,p=t.setupRoomEditorOpenMapId?.()??null,v=t.setupRoomEditorLoadingMapId?.()??null,f=t.setupRoomEditorRooms?.()??[],h=t.setupRoomEditorSaving?.()??!1,b=t.setupDeletePendingMapId?.()??null,w=t.setupDeleteStage?.()??null,S=t.setupDeleteTypedToken?.()??"",g=t.setupDeleteDeleting?.()??!1,R=new Set((t.setupRoomEditorEnabledIds?.()??[]).map(String)),y=t.setupRoomEditorFloorTypesMap?.()??{},T=(d?.maps??[]).filter(k=>k.imported),M=n?'<div class="evcc-setup-result info">Working\u2026</div>':"",J=s&&!n?`<div class="evcc-setup-result error">${this.escapeHtml(String(s))}</div>`:"",z=(()=>{if(!o||n)return"";let k=o.status??"",V=o.message??"";return k==="error"||k==="blocked"?`<div class="evcc-setup-result error">${this.escapeHtml(V)}</div>`:V?`<div class="evcc-setup-result success">${this.escapeHtml(V)}</div>`:""})(),ie={add_vacuum:k=>k.completed?`
          <div class="evcc-setup-step-body">
            Vacuum registered.
            <div class="evcc-setup-entity-id">${this.escapeHtml(a)}</div>
          </div>
        `:`
        <div class="evcc-setup-step-body">
          Register this vacuum with the integration so it can be managed.
          <div class="evcc-setup-entity-id">${this.escapeHtml(a)}</div>
        </div>
        <button class="evcc-setup-btn"
                data-action="setup-add-vacuum"
                ${n?"disabled":""}>
          Add Vacuum
        </button>
      `,import_active_map:k=>{let V=ai(u,"add_vacuum"),I=T.length;if(!V)return'<div class="evcc-setup-step-body muted">Complete Add Vacuum first.</div>';let W=I>0?`<div class="evcc-setup-step-body muted">${I} map${I===1?"":"s"} imported.</div>`:`<div class="evcc-setup-step-body">Import the vacuum's currently active map. Make sure it has completed a mapping run first.</div>`,Y=I>0?"Import Another Map":"Import Active Map",ee=I>0?"secondary":"";return`
        ${W}
        <button class="evcc-setup-btn ${ee}"
                data-action="setup-import-map"
                ${n?"disabled":""}>
          ${Y}
        </button>
      `},save_rooms:k=>{let V=u.find(D=>D.id==="import_active_map"),I=!!V,W=!V||V.completed;if(!ai(u,"add_vacuum"))return'<div class="evcc-setup-step-body muted">Complete Add Vacuum first.</div>';if(I&&!W)return'<div class="evcc-setup-step-body muted">Complete map import first.</div>';if(T.length===0&&!I)return`
          <div class="evcc-setup-step-body">
            No rooms discovered yet. Run a clean cycle so the vacuum reports
            its room list, then refresh setup status.
          </div>
        `;let ee=de(m,d),ve=T.map(D=>be(D,!0)).join("");return`
        ${k.completed?'<div class="evcc-setup-step-body muted">Rooms configured. Drift detection watches for new or removed rooms below.</div>':'<div class="evcc-setup-step-body">Configure each imported map \u2014 exclude ghost rooms and set floor types.</div>'}
        ${ee}
        <div class="evcc-setup-mapconfig-list">${ve}</div>
      `}},de=(k,V)=>{if(!k||k.in_sync)return"";let I=Array.isArray(k.new_rooms)?k.new_rooms:[],W=Array.isArray(k.removed_rooms)?k.removed_rooms:[],Y=Array.isArray(k.transiently_missing)?k.transiently_missing:[];if(I.length===0&&W.length===0&&Y.length===0)return"";let ee=I.length===0?"":`
        <div class="evcc-setup-drift-section new">
          <div class="evcc-setup-drift-title">
            New rooms discovered (${I.length})
          </div>
          <div class="evcc-setup-drift-hint">
            The vacuum reports rooms you haven't configured yet. Configure
            the matching map to include them, or reject as phantoms.
          </div>
          <div class="evcc-setup-drift-list">
            ${I.map(D=>`
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(D.name??`Room ${D.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(D.map_id??""))}</span>
                <button class="evcc-setup-btn secondary small"
                        data-action="setup-reject-room"
                        data-room-id="${D.room_id}"
                        ${n?"disabled":""}>
                  Reject as phantom
                </button>
              </div>
            `).join("")}
          </div>
        </div>
      `,ve=W.length===0?"":`
        <div class="evcc-setup-drift-section removed">
          <div class="evcc-setup-drift-title">
            Rooms no longer reported (${W.length})
          </div>
          <div class="evcc-setup-drift-hint">
            These rooms have been missing from discovery long enough to be
            confirmed removed. Reconfigure the matching map to drop them.
          </div>
          <div class="evcc-setup-drift-list">
            ${W.map(D=>`
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(D.name??`Room ${D.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(D.map_id??""))}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `,Ee=Y.length===0?"":`
        <div class="evcc-setup-drift-section transient">
          <div class="evcc-setup-drift-title">
            Temporarily missing (${Y.length})
          </div>
          <div class="evcc-setup-drift-hint">
            Missing from recent discovery passes but not yet confirmed
            removed \u2014 likely a transient API glitch. Use "Force remove"
            only if you know the room is permanently gone.
          </div>
          <div class="evcc-setup-drift-list">
            ${Y.map(D=>`
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(D.name??`Room ${D.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(D.map_id??""))}</span>
                <button class="evcc-setup-btn destructive-ghost small"
                        data-action="setup-force-remove-room"
                        data-room-id="${D.room_id}"
                        ${n?"disabled":""}>
                  Force remove now
                </button>
              </div>
            `).join("")}
          </div>
        </div>
      `;return`
        <div class="evcc-setup-drift-panel">
          ${ee}
          ${ve}
          ${Ee}
        </div>
      `},fe=k=>v===k?`<div class="evcc-setup-room-editor">
          <div class="evcc-setup-result info">Loading rooms\u2026</div>
        </div>`:p!==k?"":`
        <div class="evcc-setup-room-editor">
          <div class="evcc-setup-room-editor-hint">
            Deselect rooms you don't want managed (phantom rooms, closets, etc.).
            Set each real room's floor type \u2014 it drives the cleaning profile system.
          </div>
          <div class="evcc-setup-room-list">
            ${f.length===0?'<div class="evcc-setup-step-body muted">No rooms found for this map.</div>':f.map(I=>{let W=String(I.room_id),Y=this.escapeHtml(I.name??`Room ${W}`),ee=R.has(W),ve=y[W]??"hardwood",Ee=Pn.map(D=>`
              <button class="evcc-setup-floor-chip ${ve===D.value?"active":""}"
                      data-action="setup-set-floor-type"
                      data-room-id="${W}"
                      data-floor-type="${D.value}"
                      ${h?"disabled":""}>
                ${D.label}
              </button>
            `).join("");return`
              <div class="evcc-setup-room-row ${ee?"":"excluded"}">
                <div class="evcc-setup-room-row-top">
                  <button class="evcc-setup-room-toggle ${ee?"on":"off"}"
                          data-action="setup-toggle-room"
                          data-room-id="${W}"
                          title="${ee?"Click to exclude":"Click to include"}"
                          ${h?"disabled":""}>
                    ${ee?"\u2713":"\u2715"}
                  </button>
                  <span class="evcc-setup-room-name">${Y}</span>
                </div>
                ${ee?`<div class="evcc-setup-floor-chips">${Ee}</div>`:""}
              </div>
            `}).join("")}
          </div>
          <button class="evcc-setup-btn"
                  data-action="setup-save-rooms"
                  data-map-id="${k}"
                  ${h?"disabled":""}>
            ${h?"Saving\u2026":"Save Room Configuration"}
          </button>
        </div>
      `,ge=(k,V)=>{if(b!==k)return"";let I=this.escapeHtml(V?.typed_confirmation_value??`Map ${k}`),W=V?.requires_typed_confirmation??!1,Y=V?.reasons??[],ee=Y.length?`<div class="evcc-setup-delete-badges">
             ${Y.map(D=>`<span class="evcc-setup-protection-badge">${this.escapeHtml(D.message)}</span>`).join("")}
           </div>`:"",ve=W?`<div class="evcc-setup-delete-typed">
             <div class="evcc-setup-delete-typed-hint">
               Type <strong>${I}</strong> to confirm deletion.
             </div>
             <input class="evcc-setup-delete-input"
                    data-action="setup-delete-map-input"
                    type="text"
                    placeholder="${I}"
                    value="${this.escapeHtml(S)}"
                    autocomplete="off"
                    spellcheck="false" />
           </div>`:"",Ee=W?S.trim()===(V?.typed_confirmation_value??"").trim():!0;return`
        <div class="evcc-setup-delete-panel">
          ${ee}
          <div class="evcc-setup-delete-warning">
            Delete <strong>${I}</strong>? This removes all rooms, history,
            and learning data for this map from the integration.
            The upstream cloud map is not affected.
          </div>
          ${ve}
          <div class="evcc-setup-delete-actions">
            <button class="evcc-setup-btn destructive small"
                    data-action="setup-delete-map-confirm"
                    data-map-id="${k}"
                    ${!Ee||g?"disabled":""}>
              ${g?"Deleting\u2026":"Delete Map"}
            </button>
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-delete-map-cancel"
                    ${g?"disabled":""}>
              Cancel
            </button>
          </div>
        </div>
      `},be=(k,V)=>{let I=String(k.map_id),W=this.escapeHtml(k.display_name??`Map ${I}`),Y=t.isSetupMapConfigured?.(I),ee=p===I||v===I,ve=k.protection??null,Ee=ve?.requires_typed_confirmation??!1,D=b===I,Ac=Y&&!ee?'<span class="evcc-setup-configured-badge">\u2713 Configured</span>':"",Cc=V?`
        <button class="evcc-setup-btn ${Y?"secondary":""} small"
                data-action="setup-configure-map"
                data-map-id="${I}"
                ${n||h||g?"disabled":""}>
          ${ee?"Close":Y?"Reconfigure":"Configure Rooms"}
        </button>
      `:"",Ic=D?"":`<button class="evcc-setup-btn destructive-ghost small"
                   data-action="setup-delete-map-open"
                   data-map-id="${I}"
                   data-requires-typed="${Ee}"
                   ${n||h||g?"disabled":""}>
             Delete
           </button>`;return`
        <div class="evcc-setup-mapconfig-row">
          <div class="evcc-setup-mapconfig-header">
            <div class="evcc-setup-mapconfig-name">${W}</div>
            <div class="evcc-setup-mapconfig-actions">
              ${Ac}
              ${Ic}
              ${Cc}
            </div>
          </div>
          ${ge(I,ve)}
          ${V?fe(I):""}
        </div>
      `},E=(k,V)=>{let I=ie[k.id],W=I?I(k):`<div class="evcc-setup-step-body muted">No handler for step "${this.escapeHtml(k.id)}".</div>`,Y=k.completed?"\u2713":String(V+1);return`
        <div class="evcc-setup-step">
          <div class="evcc-setup-step-header">
            <div class="evcc-setup-step-badge ${k.completed?"done":""}">
              ${Y}
            </div>
            <div class="evcc-setup-step-label">${this.escapeHtml(k.label)}</div>
          </div>
          ${W}
        </div>
      `},q=u.map(E).join(""),U=!!c?.setup_complete,j=m?m.in_sync!==!1:!0,pe=U&&j?`<div class="evcc-setup-result success">
           \u2713 Setup complete \u2014 switch to the Rooms tab to start cleaning.
         </div>`:"",le=d?.panel_title??"",ce=d?`
      <div class="evcc-setup-rename">
        <div class="evcc-setup-rename-title">Panel name</div>
        <div class="evcc-setup-step-body muted">
          Rename this vacuum's entry in the Home Assistant sidebar. After saving,
          refresh the page to see the new name. Leave blank to reset to the default.
        </div>
        <div class="evcc-setup-rename-row">
          <input class="evcc-setup-rename-input"
                 type="text"
                 maxlength="48"
                 data-action="setup-rename-panel-input"
                 value="${this.escapeHtml(le)}"
                 placeholder="Vacuum Agent"
                 autocomplete="off"
                 spellcheck="false"
                 ${n?"disabled":""} />
          <button class="evcc-setup-btn small"
                  data-action="setup-rename-panel-save"
                  ${n?"disabled":""}>
            Rename
          </button>
        </div>
      </div>
    `:"",Le=new Set(l.map(k=>k.vacuum_entity_id));a&&Le.add(a);let Pe=(r?._hass?.states?Object.keys(r._hass.states).filter(k=>k.startsWith("vacuum.")):[]).filter(k=>!Le.has(k)).sort(),Re=Pe.map(k=>{let V=r._hass.states[k]?.attributes?.friendly_name??k;return`
        <div class="evcc-setup-add-other-row">
          <div class="evcc-setup-add-other-info">
            <span class="evcc-setup-add-other-name">${this.escapeHtml(String(V))}</span>
            <span class="evcc-setup-entity-id">${this.escapeHtml(k)}</span>
          </div>
          <button class="evcc-setup-btn small"
                  data-action="setup-add-other-vacuum"
                  data-vacuum-id="${this.escapeHtml(k)}"
                  ${n?"disabled":""}>
            Add
          </button>
        </div>
      `}).join(""),Ue=`
      <div class="evcc-setup-add-other">
        <div class="evcc-setup-add-other-title">Add another vacuum</div>
        ${Pe.length===0?'<div class="evcc-setup-step-body muted">All detected vacuums are already managed.</div>':`<div class="evcc-setup-step-body">These vacuums are available in Home Assistant but not yet managed. Adding one registers its adapter and a sidebar panel (the integration reloads).</div>
             <div class="evcc-setup-add-other-list">${Re}</div>`}
      </div>
    `,$e=`
      <div class="evcc-setup-footer">
        <button class="evcc-setup-btn secondary"
                data-action="setup-refresh"
                ${n?"disabled":""}>
          ${c==null?"Check Status":"Refresh"}
        </button>
      </div>
    `;return`
      <div class="evcc-setup-view">
        <div class="evcc-setup-header">
          <div class="evcc-setup-title">Vacuum Setup</div>
          <div class="evcc-setup-description">
            Steps below are declared by your vacuum adapter. Each must complete
            in order. New rooms discovered after setup will surface here for
            review before they enter the room library.
          </div>
        </div>

        ${q}
        ${pe}
        ${z}
        ${J}
        ${M}
        ${ce}
        ${Ue}
        ${$e}
      </div>
    `}}function ai(i,e){return Array.isArray(i)?!!i.find(r=>r.id===e)?.completed:!1}function Nn(i){if(!i)return[{id:"add_vacuum",label:"Add vacuum",completed:!1,service:""},{id:"import_active_map",label:"Import active map",completed:!1,service:""},{id:"save_rooms",label:"Configure rooms",completed:!1,service:""}];let e=!!i.has_imported_map;return[{id:"add_vacuum",label:"Add vacuum",completed:!0,service:""},{id:"import_active_map",label:"Import active map",completed:e,service:""},{id:"save_rooms",label:"Configure rooms",completed:e,service:""}]}var Fn="0 0 16 16",Dn=Object.freeze({ok:'<path d="M3.4 8.6l3 3 6.2-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',outlier:'<path d="M4.4 4.4l7.2 7.2M11.6 4.4l-7.2 7.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',warn:'<path d="M8 3.2v5.6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="8" cy="12.3" r="1.25" fill="currentColor"/>',likely:'<circle cx="8" cy="8" r="5.3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 2.7a5.3 5.3 0 0 1 0 10.6z" fill="currentColor"/>',excluded:'<path d="M3.4 8h9.2" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',baseline:'<path d="M8 2.4l5.6 5.6-5.6 5.6L2.4 8z" fill="currentColor"/>'});function xe(i){let e=Dn[i];return e?`<svg class="evcc-mrev-badge-mark" viewBox="${Fn}" aria-hidden="true" focusable="false">${e}</svg>`:""}function ci(i){i.renderMappingReviewView=function(e){let{state:t}=e,r=t.mappingBoundsSnapshot?.();if(!r)return'<div class="evcc-empty">Loading mapping bounds...</div>';if(r.available===!1)return`
        <div class="evcc-mrev-view">
          <div class="evcc-empty">${this.escapeHtml(r.message||"Mapping bounds unavailable.")}</div>
        </div>`;let a=r.rooms??{},c=t.mappingBoundsFilter?.()??"all",n=t.mappingBoundsFilterOptions?.()??[],s=Object.keys(a),o=s.filter(p=>a[p]?.bounds),l=s.filter(p=>!a[p]?.bounds),d=s.reduce((p,v)=>p+(a[v]?.job_bounds_history?.length??0),0),m=[...s.filter(p=>c==="has_bounds"?!!a[p]?.bounds:c==="no_bounds"?!a[p]?.bounds:!0)].sort((p,v)=>{let f=!!a[p]?.bounds,h=!!a[v]?.bounds;return f!==h?f?-1:1:Number(p)-Number(v)});return`
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
              ${n.map(p=>`
                <button class="evcc-chip ${c===p.value?"active":""}"
                        data-mrev-filter="${this.escapeHtml(p.value)}">
                  ${this.escapeHtml(p.label)}
                </button>
              `).join("")}
            </div>
          </div>
        </section>

        <div class="evcc-mrev-grid">
          ${m.map(p=>this._renderMappingRoomCard(p,a[p],t)).join("")}
        </div>

      </div>
    `},i._renderMappingRoomCard=function(e,t,r){let a=t?.name??`Room ${e}`,c=t?.bounds??null,n=t?.job_bounds_history??[],s=!!t?.has_archive,o=r.isMappingBoundsClearPending?.(e),l=r.isMappingRebuildPending?.(e),d=n.filter(f=>!f.excluded).length,u=n.filter(f=>f.excluded).length,p=d>=4,v=c?p?`<span class="evcc-mrev-badge evcc-mrev-badge--ok">${xe("ok")}${d} run${d!==1?"s":""} \xB7 ${c.sample_count??0} samples</span>`:`<span class="evcc-mrev-badge evcc-mrev-badge--likely">${xe("likely")}${d} run${d!==1?"s":""} \xB7 Likely</span>`:`<span class="evcc-mrev-badge evcc-mrev-badge--warn">${xe("warn")}No bounds</span>`;return`
      <div class="evcc-mrev-card">
        <div class="evcc-mrev-card-header">
          <div class="evcc-mrev-room-name">${this.escapeHtml(a)}</div>
          <div class="evcc-mrev-room-meta">
            <span class="evcc-mrev-room-id">ID ${this.escapeHtml(e)}</span>
            ${v}
            ${u>0?`<span class="evcc-mrev-badge evcc-mrev-badge--excluded">${xe("excluded")}${u} excluded</span>`:""}
          </div>
        </div>

        ${c?`<div class="evcc-mrev-bounds-block">
               ${this._renderBoundsTable(c)}
             </div>`:s?'<div class="evcc-mrev-no-bounds">No active bounds \u2014 archive available for rebuild.</div>':'<div class="evcc-mrev-no-bounds">Run solo to establish bounds.</div>'}

        ${n.length>0?`
          <div class="evcc-mrev-history">
            <div class="evcc-mrev-history-label">Run History (${n.length})</div>
            ${n.map((f,h)=>this._renderJobBoundsEntry(f,h,e,c,n,r)).join("")}
          </div>`:""}

        <div class="evcc-mrev-card-footer">
          ${!c&&s?`
            <button class="evcc-chip evcc-mrev-rebuild-btn ${l?"evcc-mrev-clear-btn--disabled":""}"
                    data-mrev-rebuild="${this.escapeHtml(e)}"
                    ${l?"disabled":""}>
              ${l?"Rebuilding\u2026":"Rebuild from Archive"}
            </button>`:""}
          <button class="evcc-chip evcc-mrev-clear-btn ${!c||o?"evcc-mrev-clear-btn--disabled":""}"
                  data-mrev-clear="${this.escapeHtml(e)}"
                  ${!c||o?"disabled":""}>
            ${o?"Clearing\u2026":"Clear All"}
          </button>
        </div>
      </div>
    `},i._renderBoundsTable=function(e){let t=Math.round(e.max_x-e.min_x),r=Math.round(e.max_y-e.min_y),a=c=>Math.round(c).toLocaleString();return`
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
    `},i._renderJobBoundsEntry=function(e,t,r,a,c,n){let s=w=>Math.round(w).toLocaleString(),o=!!e.excluded,l=n.isMappingJobActionPending?.(r,t),d=[];if(!o){let w=c.filter((S,g)=>g!==t&&!S.excluded);if(w.length>0){let S={min_x:Math.min(...w.map(y=>y.min_x)),max_x:Math.max(...w.map(y=>y.max_x)),min_y:Math.min(...w.map(y=>y.min_y)),max_y:Math.max(...w.map(y=>y.max_y))},g=(S.max_x-S.min_x)*.1,R=(S.max_y-S.min_y)*.1;e.max_x>S.max_x+g&&d.push("max X"),e.min_x<S.min_x-g&&d.push("min X"),e.max_y>S.max_y+R&&d.push("max Y"),e.min_y<S.min_y-R&&d.push("min Y")}}let u=d.length>0,m=this._mrevFmtJobId(e.job_id),p=e.recorded_at?this._mrevFmtDate(e.recorded_at):"",v=t===c.length-1,f=c.filter(w=>!w.excluded).length,h=!o&&!l&&!v&&f>1,b=o&&!l&&!v;return`
      <div class="evcc-mrev-job-entry ${o?"evcc-mrev-job-entry--excluded":""} ${u?"evcc-mrev-job-entry--outlier":""}">
        <div class="evcc-mrev-job-header">
          <span class="evcc-mrev-job-id ${o?"evcc-mrev-job-id--excluded":""}">${this.escapeHtml(m)}</span>
          ${p?`<span class="evcc-mrev-job-date">${this.escapeHtml(p)}</span>`:""}
          ${o?`<span class="evcc-mrev-badge evcc-mrev-badge--excluded">${xe("excluded")}Excluded</span>`:u?`<span class="evcc-mrev-badge evcc-mrev-badge--outlier">${xe("outlier")}Outlier: ${this.escapeHtml(d.join(", "))}</span>`:`<span class="evcc-mrev-badge evcc-mrev-badge--ok">${xe("ok")}OK</span>`}
          ${v?`<span class="evcc-mrev-badge evcc-mrev-badge--baseline">${xe("baseline")}Baseline</span>`:""}
          <div class="evcc-mrev-job-actions">
            ${h?`
              <button class="evcc-chip evcc-chip--sm evcc-mrev-job-action-btn"
                      data-mrev-job-action="exclude"
                      data-mrev-room-id="${this.escapeHtml(r)}"
                      data-mrev-job-index="${t}">
                Exclude
              </button>`:""}
            ${b?`
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
    `},i._mrevFmtJobId=function(e){if(!e)return"Unknown";if(e==="pre_migration")return"Pre-migration";let t=String(e).match(/job_(\d{4}-\d{2}-\d{2})T(\d{2}-\d{2})/);return t?`${t[1]} ${t[2].replace("-",":")}`:String(e).slice(-16)},i._mrevFmtDate=function(e){if(!e)return"";try{return new Date(e).toLocaleString(void 0,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}catch{return String(e).slice(0,16)}}}function ni(i){i._renderReviewSubtabStrip=function(e){let t=e.reviewSubtab(),r=e.externalPendingRuns().length,a=r>0?`External Jobs (${r})`:"External Jobs";return`
      <div class="evcc-review-subtabs">
        <button class="evcc-review-subtab ${t==="history"?"is-active":""}"
                data-action="set-review-subtab" data-subtab="history">Learning History</button>
        <button class="evcc-review-subtab ${t==="external"?"is-active":""}"
                data-action="set-review-subtab" data-subtab="external">${a}</button>
      </div>
    `},i.renderExternalJobsSubtab=function(e){let{state:t}=e,r=t.externalPendingRuns();if(!r.length){let a=t.externalBrand?.();return`
        <div class="evcc-empty evcc-external-empty">
          No app-started runs awaiting review. Start a clean from ${a?`the ${this.escapeHtml(a)} app`:"your robot's app"} and the
          run will appear here to confirm which rooms it cleaned.
        </div>
      `}return`<div class="evcc-external-list">${r.map(a=>this._renderExternalRunCard(a)).join("")}</div>`},i._renderExternalRunCard=function(e){let t=Array.isArray(e.segments)?e.segments:[],r=t.reduce((s,o)=>s+(Number(o.area_m2)||0),0),a=this._formatReviewTimestamp&&this._formatReviewTimestamp(e.detection_ts)||e.detection_ts||"Unknown time",c=e.suggested_room_count??t.length,n=this.escapeHtml(String(e.pending_job_id||""));return`
      <div class="evcc-external-card">
        <div class="evcc-external-card-main">
          <div class="evcc-external-card-title">${this.escapeHtml(String(a))}</div>
          <div class="evcc-external-card-meta">
            ~${c} room${c===1?"":"s"} \xB7 ${r.toFixed(0)} m\xB2 \xB7
            ${t.length} segment${t.length===1?"":"s"}
          </div>
        </div>
        <div class="evcc-external-card-actions">
          <button class="evcc-btn evcc-btn-primary" data-action="open-external-wizard" data-pending-id="${n}">Review</button>
          <button class="evcc-btn evcc-btn-ghost" data-action="discard-external-run" data-pending-id="${n}">Discard</button>
        </div>
      </div>
    `},i.renderExternalWizardModal=function(e){let{state:t}=e;if(!t.isExternalWizardOpen())return"";let r=t.externalWizard(),a=t.externalWizardGroups(),c=r.step===1?this._renderExtWizardStep1(r,a):this._renderExtWizardStep2(e,r,a);return`
      <div class="evcc-modal-backdrop" data-action="close-external-wizard">
        <div class="evcc-modal evcc-external-wizard-modal" data-stop-propagation>
          <div class="evcc-modal-header">
            <div class="evcc-modal-title">Review app-started run</div>
            <div class="evcc-modal-subtitle">Step ${r.step} of 2 \u2014 ${r.step===1?"how many rooms?":"name each room"}</div>
          </div>
          <div class="evcc-modal-body">
            ${r.error?`<div class="evcc-external-error">${this.escapeHtml(String(r.error))}</div>`:""}
            ${c}
          </div>
          ${this._renderExtWizardFooter(r,a)}
        </div>
      </div>
    `},i._renderExtWizardStep1=function(e,t){return e.resegmentable?this._renderExtWizardStep1V2(e):this._renderExtWizardStep1Legacy(e,t)},i._segFacts=function(e){let t=e.settings||{};return`${(Number(e.area_m2)||0).toFixed(0)} m\xB2 \xB7 ${Math.round((Number(e.time_wall_s)||0)/60)} min \xB7 ${this.escapeHtml(String(t.clean_mode||"?"))} \xB7 ${e.pass_count||1}\xD7`},i._renderExtWizardStep1V2=function(e){let t=e.segments||[],r=t.length,a=Array.isArray(e.candidates)?e.candidates:[],c=a.length+1,n=!!e.busy,s=new Set((e.activeBoundaries||[]).map(Number)),o=a.filter(v=>!s.has(Number(v.id))),l=t.map((v,f)=>f===0?0:Number(v.boundary_id)),d=v=>v+1<t.length?l[v+1]:1/0,u=`
      <div class="evcc-ext-count">
        <span class="evcc-ext-count-label">Rooms</span>
        <div class="evcc-ext-stepper">
          <button class="evcc-btn evcc-ext-step" data-action="ext-count-dec" ${n||r<=1?"disabled":""}>\u2212</button>
          <strong class="evcc-ext-count-n">${r}</strong>
          <button class="evcc-btn evcc-ext-step" data-action="ext-count-inc" ${n||r>=c?"disabled":""}>+</button>
        </div>
        <span class="evcc-ext-hint">set the room count, or split / merge below</span>
      </div>`,m=t.map((v,f)=>{let h=v.boundary_id,b=f===0?'<span class="evcc-ext-seg-start">First room</span>':`<button class="evcc-ext-merge" data-action="ext-merge-up" data-boundary-id="${h}" ${n?"disabled":""}>\u21A5 Merge up</button>`,S=o.filter(g=>Number(g.id)>l[f]&&Number(g.id)<d(f)).map(g=>`
        <button class="evcc-ext-split-here" data-action="ext-split-here" data-boundary-id="${g.id}" ${n?"disabled":""}>
          \u21B3 Split here${g.confident?"":" \xB7 uncertain"}
        </button>`).join("");return`
        <div class="evcc-ext-seg is-v2">
          <div class="evcc-ext-seg-row">
            ${b}
            <span class="evcc-ext-seg-facts">Room ${f+1} \xB7 ${this._segFacts(v)}</span>
          </div>
          ${S?`<div class="evcc-ext-splits">${S}</div>`:""}
        </div>`}).join(""),p=e.resegmentMeta&&e.resegmentMeta.capped?`<div class="evcc-ext-blocked">${this.escapeHtml(String(e.resegmentMeta.message||"Capped to the detectable room count."))}</div>`:"";return`${u}${p}<div class="evcc-ext-seglist">${m}</div>`},i._renderExtWizardStep1Legacy=function(e,t){let r=(e.segments||[]).map(a=>{let c=Number(a.order??0),n;if(c===0)n='<div class="evcc-ext-seg-start">First room</div>';else{let s=!!e.splits[c],o=!!a.confident_boundary;n=`
          <button class="evcc-ext-split ${s?"is-split":"is-merged"}"
                  data-action="toggle-external-split" data-order="${c}">
            ${s?"\u2702 split here":"\u21B3 merged"}${o?"":" \xB7 uncertain"}
          </button>`}return`<div class="evcc-ext-seg">${n}<div class="evcc-ext-seg-facts">seg ${c} \xB7 ${this._segFacts(a)}</div></div>`}).join("");return`
      <div class="evcc-ext-count">
        Detected <strong>${t.length}</strong> room${t.length===1?"":"s"}.
        Merge any over-split before continuing.
      </div>
      <div class="evcc-ext-seglist">${r}</div>
    `},i._renderExtWizardStep2=function(e,t,r){return r.map((a,c)=>this._renderExtRoomPanel(e,t,a,c)).join("")},i._renderExtRoomPanel=function(e,t,r,a){let c=r.lead||{},n=Number(c.order??0),s=t.assignments[n]||{overrides:{}},o=(r.segments||[]).reduce((y,T)=>y+(Number(T.area_m2)||0),0),l=c.settings||{},d=s.overrides||{},m=(Array.isArray(c.shortlist)?c.shortlist:[]).map(y=>`
      <button class="evcc-chip ${s.room_id===y.room_id?"active":""}"
              data-action="ext-pick-room" data-order="${n}" data-room-id="${y.room_id}">
        ${this.escapeHtml(String(y.name||y.slug||y.room_id))}${y.learned_area_m2?` \xB7 ${Number(y.learned_area_m2).toFixed(0)} m\xB2`:""}
      </button>`).join(""),p=d.clean_mode??l.clean_mode,v=[["vacuum","Vacuum"],["vacuum_mop","Vac & Mop"],["mop","Mop"]].map(([y,T])=>`<button class="evcc-chip ${p===y?"active":""}"
        data-action="ext-set-override" data-order="${n}" data-key="clean_mode" data-value="${y}">${T}</button>`).join(""),f=Number(d.clean_passes??c.pass_count??1),h=[1,2].map(y=>`<button class="evcc-chip ${f===y?"active":""}"
      data-action="ext-set-override" data-order="${n}" data-key="clean_passes" data-value="${y}">${y}\xD7</button>`).join(""),b=p==="mop"||p==="vacuum_mop",w=y=>typeof e.state[y]=="function"?e.state[y]():[],S=this._extSettingRow(n,"Suction","fan_speed",w("suctionLevelOptions"),d.fan_speed??l.fan_speed),g=this._extSettingRow(n,"Cleaning Path","clean_intensity",w("cleanIntensityOptions"),d.clean_intensity??l.clean_intensity),R=b?this._extSettingRow(n,"Water","water_level",w("waterLevelOptions"),d.water_level??l.water_level):"";return`
      <div class="evcc-ext-room">
        <div class="evcc-ext-room-head">Room ${a+1} \xB7 ${o.toFixed(0)} m\xB2
          ${r.orders.length>1?`\xB7 ${r.orders.length} segments merged`:""}</div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Which room?</div>
          <div class="evcc-chip-row">${m}${this._extAllRoomsOptions(e,n,s.room_id)}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Mode</div>
          <div class="evcc-chip-row">${v}</div>
        </div>
        <div class="evcc-editor-field-group">
          <div class="evcc-field-label">Passes</div>
          <div class="evcc-chip-row">${h}</div>
        </div>
        ${S}
        ${g}
        ${R}
        <div class="evcc-editor-field-group evcc-ext-edge">
          <div class="evcc-field-label">Edge mop? <span class="evcc-ext-hint">not detected \u2014 please set</span></div>
          <div class="evcc-chip-row">
            <button class="evcc-chip ${s.edge_mopping?"active":""}"
              data-action="ext-set-edge" data-order="${n}" data-value="true">On</button>
            <button class="evcc-chip ${s.edge_mopping?"":"active"}"
              data-action="ext-set-edge" data-order="${n}" data-value="false">Off</button>
          </div>
        </div>
      </div>
    `},i._extSettingRow=function(e,t,r,a,c){if(!Array.isArray(a)||!a.length)return"";let n=String(c??""),s=a.map(o=>{let l=String(o.value??"");return`<button class="evcc-chip ${n&&n.toLowerCase()===l.toLowerCase()?"active":""}"
        data-action="ext-set-override" data-order="${e}" data-key="${r}"
        data-value="${this.escapeHtml(l)}">${this.escapeHtml(String(o.label||l))}</button>`}).join("");return`
      <div class="evcc-editor-field-group">
        <div class="evcc-field-label">${this.escapeHtml(t)}</div>
        <div class="evcc-chip-row">${s}</div>
      </div>`},i._extAllRoomsOptions=function(e,t,r){let a=e.state.externalWizard?.(),c=Array.isArray(a?.rooms)?a.rooms:[];if(!c.length)return"";let n=c.map(s=>{let o=s.room_id??s.id,l=s.name||s.slug||o,d=String(o)===String(r)?"selected":"";return`<option value="${o}" ${d}>${this.escapeHtml(String(l))}</option>`}).join("");return`
      <select class="evcc-ext-allrooms" data-action="ext-pick-room-select" data-order="${t}">
        <option value="">\u2026 pick another room</option>${n}
      </select>`},i._renderExtWizardFooter=function(e,t){let r=Array.isArray(e.blocked)?e.blocked:[],a=r.length?`<div class="evcc-ext-blocked">\u26A0 ${r.length} room${r.length===1?"":"s"} don't match the picked area \u2014 re-pick, or keep anyway.</div>`:"",c,n;return e.step===1?(c='<button class="evcc-btn evcc-btn-ghost" data-action="close-external-wizard">Cancel</button>',n='<button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-next">Next: name rooms \u2192</button>'):(c='<button class="evcc-btn evcc-btn-ghost" data-action="ext-wizard-back">\u2190 Back</button>',n=`
        <button class="evcc-btn evcc-btn-primary" data-action="ext-wizard-confirm" ${e.busy?"disabled":""}>
          ${e.busy?"Saving\u2026":"Confirm"}
        </button>
        ${r.length?'<button class="evcc-btn evcc-btn-warn" data-action="ext-wizard-override">Keep anyway</button>':""}`),`<div class="evcc-modal-footer">${a}<div class="evcc-modal-footer-row">${c}${n}</div></div>`}}var _={ROOMS:"rooms",MAINTENANCE:"maintenance",BASE_STATION:"base_station",METRICS:"metrics",LEARNING_REVIEW:"learning_review",ROOM_RULES:"room_rules",THEME:"theme",MAPPING_ARCHIVE:"mapping",MAP_CONFIG:"map_config",MAPPING_REVIEW:"mapping_review",SETUP:"setup"},at=[_.ROOMS,_.MAINTENANCE,_.BASE_STATION,_.METRICS,_.LEARNING_REVIEW,_.ROOM_RULES,_.THEME,_.MAP_CONFIG,_.MAPPING_REVIEW,_.SETUP];function we(i,e){return i===_.BASE_STATION?e?.supportsBaseStation?.()!==!1:i===_.MAPPING_REVIEW?e?.supportsMapBounds?.()!==!1:!0}function oi(i){let e=i._state,t=i._renderers;return{card:i,state:e,renderers:t,vacuumName:e.vacuumDisplayName(),vacuumStatus:e.vacuumState()??"unknown",vacuumStatusLabel:e.vacuumStateLabel?.()??null,dockStatus:e.dockStatus?.()??null,dockStatusLabel:e.dockStatusLabel?.()??null,battery:e.batteryLevel(),view:i._view??_.ROOMS}}function Hn(i){return{cleaning:"cleaning",docked:"docked",returning:"returning",error:"error",paused:"paused"}[i]||""}function si(i){return String(i??"").replace(/[_-]+/g," ").replace(/\s+/g," ").trim().replace(/\w\S*/g,e=>e.charAt(0).toUpperCase()+e.slice(1).toLowerCase())}function zn(i){let e=String(i??"").trim().toLowerCase();return{cleaning:"cleaning",washing:"cleaning",drying:"returning",emptying:"returning",charging:"charging",error:"error",fault:"error",offline:"offline",unavailable:"unavailable",idle:"docked",standby:"docked"}[e]||""}function li(i){let{state:e,renderers:t,vacuumName:r,vacuumStatus:a,vacuumStatusLabel:c,dockStatus:n,dockStatusLabel:s,battery:o,view:l}=i,d=o!=null?`${o}%`:"",u=c??si(a),m=s??(n?si(n):"");return`
    <div class="evcc-header">

      <div class="evcc-header-left">
        <div class="evcc-vacuum-name">
          ${t.escapeHtml(r)}
        </div>

        <div class="evcc-vacuum-status">
          <span class="evcc-status-dot ${Hn(a)}"></span>
          <span class="evcc-status-prefix">Vacuum Status:</span>
          <span>${t.escapeHtml(u)}</span>
          ${d?`<span class="evcc-battery">${t.escapeHtml(d)}</span>`:""}
        </div>

        ${m?`
          <div class="evcc-vacuum-status evcc-dock-status">
            <span class="evcc-status-dot ${zn(n)}"></span>
            <span class="evcc-status-prefix">Dock Status:</span>
            <span>${t.escapeHtml(m)}</span>
          </div>
        `:""}
      </div>

    </div>

    <div class="evcc-nav">

      <button class="evcc-nav-tab ${l===_.ROOMS?"active":""}"
              data-view="${_.ROOMS}">
        Rooms
      </button>

      <button class="evcc-nav-tab ${l===_.MAINTENANCE?"active":""}"
              data-view="${_.MAINTENANCE}">
        Maintenance
      </button>

      ${we(_.BASE_STATION,e)?`
      <button class="evcc-nav-tab ${l===_.BASE_STATION?"active":""}"
              data-view="${_.BASE_STATION}">
        Base Station
      </button>
      `:""}

      <button class="evcc-nav-tab ${l===_.METRICS?"active":""}"
              data-view="${_.METRICS}">
        Metrics
      </button>

      <button class="evcc-nav-tab ${l===_.LEARNING_REVIEW?"active":""}"
              data-view="${_.LEARNING_REVIEW}">
        Learning Review
      </button>

      <button class="evcc-nav-tab ${l===_.ROOM_RULES?"active":""}"
              data-view="${_.ROOM_RULES}">
        Room Rules
      </button>

      <button class="evcc-nav-tab ${l===_.THEME?"active":""}"
              data-view="${_.THEME}">
        Theme
      </button>

      ${we(_.MAPPING_REVIEW,e)?`
      <button class="evcc-nav-tab ${l===_.MAPPING_REVIEW?"active":""}"
              data-view="${_.MAPPING_REVIEW}">
        Map Bounds
      </button>
      `:""}

      <button class="evcc-nav-tab ${l===_.SETUP?"active":""}"
              data-view="${_.SETUP}">
        Setup
      </button>

    </div>
  `}function di(i){let{view:e,renderers:t}=i;switch(e){case _.ROOMS:return t.renderRoomsView?.(i)??'<div class="evcc-empty">Rooms view unavailable</div>';case _.MAINTENANCE:return t.renderMaintenanceView?.(i)??'<div class="evcc-empty">Maintenance view unavailable</div>';case _.BASE_STATION:return t.renderBaseStationView?.(i)??'<div class="evcc-empty">Base station view unavailable</div>';case _.METRICS:return t.renderMetricsView?.(i)??'<div class="evcc-empty">Metrics view unavailable</div>';case _.LEARNING_REVIEW:return t.renderLearningReviewView?.(i)??'<div class="evcc-empty">Learning review view unavailable</div>';case _.ROOM_RULES:return t.renderRoomRulesView?.(i)??'<div class="evcc-empty">Room rules view unavailable</div>';case _.THEME:return t.renderThemeView?.(i)??'<div class="evcc-empty">Theme view unavailable</div>';case _.MAP_CONFIG:return t.renderMapConfigView?.(i)??'<div class="evcc-empty">Map config unavailable</div>';case _.MAPPING_REVIEW:return t.renderMappingReviewView?.(i)??'<div class="evcc-empty">Mapping bounds review unavailable</div>';case _.SETUP:return t.renderSetupView?.(i)??'<div class="evcc-empty">Setup unavailable</div>';default:return'<div class="evcc-empty">Unknown view</div>'}}var Bn=[{id:_.ROOMS,label:"Rooms",icon:qn()},{id:_.MAINTENANCE,label:"Upkeep",icon:Gn()},{id:_.BASE_STATION,label:"Dock",icon:Un()},{id:_.METRICS,label:"Stats",icon:Wn()}],ui=[{id:_.LEARNING_REVIEW,label:"Learning Review"},{id:_.ROOM_RULES,label:"Room Rules"},{id:_.THEME,label:"Theme"},{id:_.MAP_CONFIG,label:"Map Config"},{id:_.MAPPING_REVIEW,label:"Map Bounds"},{id:_.SETUP,label:"Setup"}];function jn(i){return{cleaning:"cleaning",docked:"docked",returning:"returning",error:"error",paused:"paused"}[i]||""}function mi(i){return String(i??"").replace(/[_-]+/g," ").replace(/\s+/g," ").trim().replace(/\w\S*/g,e=>e.charAt(0).toUpperCase()+e.slice(1).toLowerCase())}function Vn(i){let e=String(i??"").trim().toLowerCase();return{cleaning:"cleaning",washing:"cleaning",drying:"returning",emptying:"returning",charging:"charging",error:"error",fault:"error",offline:"offline",unavailable:"unavailable",idle:"docked",standby:"docked"}[e]||""}function pi(i){i.renderMobileHeader=function(e){let{vacuumName:t,vacuumStatus:r,vacuumStatusLabel:a,dockStatus:c,dockStatusLabel:n,battery:s}=e,o=s!=null?`${s}%`:"",l=a??mi(r),d=n??(c?mi(c):"");return`
      <div class="evcc-mobile-header">
        <div class="evcc-mobile-vacuum-name">
          ${this.escapeHtml(t)}
        </div>
        <div class="evcc-mobile-vacuum-status">
          <span class="evcc-status-dot ${jn(r)}"></span>
          <span class="evcc-mobile-vacuum-status-label">
            <span class="evcc-status-prefix">Vacuum Status:</span>
            ${this.escapeHtml(l)}
          </span>
          ${o?`<span class="evcc-mobile-battery">${this.escapeHtml(o)}</span>`:""}
        </div>
        ${d?`
          <div class="evcc-mobile-vacuum-status evcc-mobile-dock-status">
            <span class="evcc-status-dot ${Vn(c)}"></span>
            <span class="evcc-mobile-vacuum-status-label">
              <span class="evcc-status-prefix">Dock Status:</span>
              ${this.escapeHtml(d)}
            </span>
          </div>
        `:""}
      </div>
    `},i.renderMobileBottomNav=function(e){let t=e?.view,r=e?.state,a=Bn.filter(n=>we(n.id,r)),c=ui.some(n=>n.id===t);return`
      <nav class="evcc-mobile-nav" aria-label="Primary">
        ${a.map(n=>`
          <button
            class="evcc-mobile-nav-tab${t===n.id?" active":""}"
            data-view="${n.id}"
            aria-label="${this.escapeHtml(n.label)}"
            aria-current="${t===n.id?"page":"false"}"
          >
            <span class="evcc-mobile-nav-icon">${n.icon}</span>
            <span class="evcc-mobile-nav-label">${this.escapeHtml(n.label)}</span>
          </button>
        `).join("")}
        <button
          class="evcc-mobile-nav-tab evcc-mobile-nav-tab--more${c?" active":""}"
          data-action="mobile-more-toggle"
          aria-label="More"
          aria-haspopup="menu"
        >
          <span class="evcc-mobile-nav-icon">${Jn()}</span>
          <span class="evcc-mobile-nav-label">More</span>
        </button>
      </nav>
    `},i.renderMobileOverlay=function(e){if(!e.card?._mobileMoreOpen)return"";let t=e.view;return`
      <div class="evcc-mobile-more-backdrop"
           data-action="mobile-more-close"
           aria-hidden="true"></div>
      <div class="evcc-mobile-more-sheet"
           role="menu"
           aria-label="Additional views">
        <div class="evcc-mobile-more-handle"></div>
        ${ui.filter(a=>we(a.id,e.state)).map(a=>`
          <button
            class="evcc-mobile-more-item${t===a.id?" active":""}"
            data-view="${a.id}"
            data-action="mobile-more-select"
            role="menuitem"
          >
            ${this.escapeHtml(a.label)}
          </button>
        `).join("")}
      </div>
    `}}function qn(){return`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M3 12 12 3l9 9"/>
    <path d="M5 10v10h14V10"/>
  </svg>`}function Gn(){return`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6.6 6.6 3 3 6.6-6.6a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2-2z"/>
  </svg>`}function Un(){return`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="3" y="9"  width="18" height="12" rx="1.5"/>
    <path d="M6 9V5h12v4"/>
    <line x1="9" y1="14" x2="15" y2="14"/>
  </svg>`}function Wn(){return`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <line x1="4" y1="20" x2="20" y2="20"/>
    <rect x="6"  y="11" width="3" height="9"/>
    <rect x="11" y="6"  width="3" height="14"/>
    <rect x="16" y="14" width="3" height="6"/>
  </svg>`}function Jn(){return`<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <circle cx="5"  cy="12" r="2"/>
    <circle cx="12" cy="12" r="2"/>
    <circle cx="19" cy="12" r="2"/>
  </svg>`}function vi(i){i.renderToasts=function(e){let t=e?.state?.activeToasts?.()??[];return t.length?`
      <div class="evcc-toast-stack">
        ${t.map(r=>`
          <div
            class="evcc-toast evcc-toast--${this.escapeHtml(r.kind)}"
            data-toast-id="${this.escapeHtml(r.id)}"
            role="status"
          >
            <span class="evcc-toast-message">${this.escapeHtml(r.message)}</span>
            <button
              type="button"
              class="evcc-toast-dismiss"
              data-action="dismiss-toast"
              data-toast-id="${this.escapeHtml(r.id)}"
              aria-label="Dismiss"
            >x</button>
          </div>
        `).join("")}
      </div>
    `:""}}function hi(i){i.renderIncompleteRunBanner=function(e){if(!e.hasIncompleteRunLog?.()||e.learningJobActive?.())return"";let t=e.incompleteRunLog(),r=e.incompleteRunMissedRooms(),a=r.length,c=String(t?.outcome_status??"cancelled").toLowerCase(),n={cancelled:"cancelled",failed:"failed",interrupted:"interrupted"}[c]??c,s=r.map(o=>`<span class="evcc-incomplete-run-room">${this.escapeHtml(o.name)}</span>`).join("");return`
      <div class="evcc-incomplete-run-banner" role="alert">
        <div class="evcc-incomplete-run-body">
          <div class="evcc-incomplete-run-title">
            Last run ${this.escapeHtml(n)} \u2014
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
      `;let r=this._formatLearningDuration(t.total_minutes),a=this._formatLearningWallClock(t.job_eta_at),c=t.confidence_breakpoint??null,n=this._formatLearningWallClock(t.stats_rebuilt_at),s=e.dashboardPlannedWaterEstimate?.(),o=e.dashboardStartStatus?.()??{},l=t.overhead??{},d=l.mop_wash??{},u=String(d.mode??"")==="by_time"&&Number(d.cycle_count??0)>0?`${this._formatLearningMinutes(l.mop_wash_minutes)} (${d.cycle_count} cycle${Number(d.cycle_count)===1?"":"s"} \xD7 ${this._formatLearningMinutes(d.minutes_per_cycle)} every ${this._formatLearningMinutes(d.interval_minutes)})`:"0 min (no cycles scheduled)";return`
      <div class="evcc-learning-panel evcc-learning-panel--prejob">
        <div class="evcc-learning-panel-header">
          <div class="evcc-learning-panel-title-group">
            <div class="evcc-learning-panel-title">Estimated Job Time</div>
            <div class="evcc-learning-panel-subtitle">
              ${this.escapeHtml(r)}
              ${a?` \xB7 done by ${this.escapeHtml(a)}`:""}
            </div>
          </div>

          ${this.renderConfidenceChip(c,this._learningConfidenceLabel(t.confidence_label,"job"))}
        </div>

        ${t.stats_stale?`
          <div class="evcc-learning-notice evcc-learning-notice--stale">
            \u26A0 Estimates may be outdated${n?` (last rebuilt ${this.escapeHtml(n)})`:""}
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
    `},i.renderLearningLiveBanner=function(e){if(!e.shouldShowLiveQueue())return"";let t=e.learningLiveBannerRoom(),r=e.learningAllCompleted?.()??!1,a=!!e.learningBatteryWarning?.(),c=r?"all-complete":String(t?.room_id??"pending");return`
      <div
        class="evcc-learning-live-banner evcc-learning-live-banner--animated"
        data-learning-key="${this.escapeHtml(c)}"
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

      ${(()=>{let n=e.dashboardJobProgress?.();if(!n?.stall_detected)return"";let s=Number(n.stall_elapsed_minutes),o=Number(n.stall_expected_minutes),l=Number.isFinite(s)?this._formatLearningMinutes(s):null,d=Number.isFinite(o)?this._formatLearningMinutes(o):null,u=l&&d?` (${l} elapsed, expected ${d})`:l?` (${l} elapsed)`:"";return`
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
    `},i._renderLearningWaterEstimateChips=function(e){if(!e||e.available===!1)return"";let t=Array.isArray(e.rooms)?e.rooms:[],r=Number(e.estimated_total_dock_clean_water_used_ml),a=Number(e.wash_cycle_count??0),c=0,n=0,s=0;for(let l of t){let d=String(l.clean_mode??"").includes("vacuum"),u=!!l.mop_active;d&&u?s++:d?c++:u&&n++}if(c+n+s===0)return"";let o=[];return Number.isFinite(r)&&r>0&&o.push(`~${this._formatLearningMilliliters(r)} water`),c>0&&o.push(`${c} vacuum-only room${c===1?"":"s"}`),n>0&&o.push(`${n} mop-only room${n===1?"":"s"}`),s>0&&o.push(`${s} vacuum + mop room${s===1?"":"s"}`),a>0&&o.push(`${a} wash cycle${a===1?"":"s"}`),o.length?`
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
    `},i._formatLearningMinutes=function(e){let t=Number(e);return Number.isFinite(t)?`${t.toFixed(1).replace(/\.0$/,"")} min`:"0 min"},i._formatLearningDuration=function(e){let t=Number(e);if(!Number.isFinite(t))return"0 min";let r=Math.round(t),a=Math.floor(r/60),c=r%60;return a<=0?`${c} min`:c<=0?`${a}h`:`${a}h ${c}m`},i._formatLearningMilliliters=function(e){let t=Number(e);return Number.isFinite(t)?`${Math.round(t)} ml`:"Unknown"},i._formatLearningWallClock=function(e){return this.formatTimestamp(e,{hour:"numeric",minute:"2-digit"},"")},i._learningConfidenceLabel=function(e,t="room"){let r=String(e??"").trim().toLowerCase();if(!r)return"";let a=r.charAt(0).toUpperCase()+r.slice(1);return t==="job"?`${a} confidence`:a},i.renderLearningSummary=function(e){if(!e.hasLearningSummary())return"";let t=e.learningSummary(),r=this._formatLearningDuration(t.total_minutes),a=this._formatLearningWallClock(t.finished_at),c=Number(t.predicted_total_minutes??t.predicted_minutes),n=Number.isFinite(c),s=n?Number(t.total_minutes)-c:null,o=Number.isFinite(s)?`${s>0?"+":""}${this._formatLearningDuration(Math.abs(s))}`:"";return`
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

        ${n?`
          <div class="evcc-learning-summary-stat">
            <div class="evcc-learning-summary-value">${this.escapeHtml(this._formatLearningDuration(c))}</div>
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
  `}}var F=class{constructor(e){this.card=e}sync(e){return this.card=e,this}};Ia(F.prototype);Oa(F.prototype);La(F.prototype);Pa(F.prototype);Na(F.prototype);Fa(F.prototype);Da(F.prototype);Ha(F.prototype);za(F.prototype);Ba(F.prototype);ja(F.prototype);Va(F.prototype);Qa(F.prototype);Za(F.prototype);ti(F.prototype);ri(F.prototype);hi(F.prototype);ii(F.prototype);ci(F.prototype);ni(F.prototype);pi(F.prototype);vi(F.prototype);function fi(i){i._bindNav=function(){this.card._onAll("[data-view]","click",e=>{let t=e.currentTarget.dataset.view;t&&this.card.setView(t)})}}function gi(i){i._bindBaseStation=function(){this.card._onAll("[data-pause-timeout-minutes]","click",async e=>{let t=e.currentTarget?.dataset?.pauseTimeoutMinutes,r=Number(t);if(!(!Number.isFinite(r)||!this.card._actions))try{let a=await this.card._actions.setPauseTimeoutSettings?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),pause_timeout_minutes_default:r});if(a){this.card._state.setPauseTimeoutSettings?.(a);let c=r===0?"Auto-cancel disabled":`Pause timeout set to ${r} min`;this.card.showToast?.(c,{kind:"success"})}else this.card.showToast?.("Could not save pause timeout",{kind:"error"});this.card._scheduleRender()}catch(a){console.error("[eufy-vacuum-command-center] Failed to set pause timeout:",a),this.card.showToast?.("Could not save pause timeout",{kind:"error"})}}),this.card._onAll("[data-dock-action]","click",async e=>{let t=e.currentTarget?.dataset?.dockAction;if(!t||!this.card._actions)return;let a={wash_mop:"washMop",dry_mop:"dryMop",stop_dry_mop:"stopDryMop",empty_dust:"emptyDust"}[t];if(!a||typeof this.card._actions[a]!="function")return;this.card._state.beginDockAction?.(t),this.card._scheduleRender();let c={wash_mop:"Mop wash sent",dry_mop:"Mop dry sent",stop_dry_mop:"Stop drying sent",empty_dust:"Dust empty sent"},n=!1;try{n=await this.card._actions[a]()!==null}finally{this.card._state.endDockAction?.(),await this.card.refreshDashboardSnapshot?.(),await this.card.refreshDockActionStatus?.(),this.card._scheduleRender()}this.card.showToast?.(n?c[t]??"Dock action sent":`Dock action failed (${t.replace(/_/g," ")})`,{kind:n?"success":"error"})})}}function bi(i){i._bindMaintenance=function(){this.card._onAll("[data-maintenance-tab]","click",e=>{let t=e.currentTarget?.dataset?.maintenanceTab;t&&(this.card._state.setMaintenanceActiveTab?.(t),this.card._scheduleRender())}),this.card._onAll("[data-action='open-maintenance-modal']","click",e=>{let t=e.currentTarget,r=t?.dataset?.itemKind,a=t?.dataset?.itemComponent,c=t?.dataset?.itemEntityId;if(!r||!a)return;let n=this.card._state.findUpkeepItem?.(r,a,c);n&&(this.card._state.openMaintenanceModal?.(n),this.card._scheduleRender())})},i._bindMaintenanceModalHost=function(e){e&&(e.querySelectorAll("[data-action='close-maintenance-modal']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.closeMaintenanceModal?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='begin-maintenance-reset']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.beginMaintenanceResetConfirmation?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='cancel-maintenance-reset']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.cancelMaintenanceResetConfirmation?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='save-maintenance-interval']").forEach(t=>{this.card._on(t,"click",async()=>{let r=e.querySelector("[data-role='maintenance-interval-input']");if(!r)return;let a=String(r.value??"").trim(),c=Number(a);if(!Number.isFinite(c)||c<=0){console.warn("[eufy-vacuum-command-center] interval must be > 0",{raw:a});return}let n=r.getAttribute("max"),s=Number(n);if(Number.isFinite(s)&&s>0&&c>s){console.warn("[eufy-vacuum-command-center] interval exceeds max",{value:c,max:s});return}let o=r.dataset?.vacuumEntityId,l=r.dataset?.component;if(!o||!l)return;if(await this.card._actions.callNamedService?.("eufy_vacuum.set_maintenance_interval",{vacuum_entity_id:o,component:l,interval_hours:c},!0)===null){console.warn("[eufy-vacuum-command-center] set_maintenance_interval failed"),this.card.showToast?.("Could not save interval",{kind:"error"});return}await this.card.refreshDashboardSnapshot?.(),this.card.showToast?.(`Interval saved (${c}h)`,{kind:"success"});let u=this.card._state.activeMaintenanceModalItem?.();if(u){let m=this.card._state.findUpkeepItem?.(u.kind,u.component,u.entity_id);m&&this.card._state.openMaintenanceModal?.(m)}this.card._scheduleRender()})}),e.querySelectorAll("[data-action='reset-maintenance-interval-default']").forEach(t=>{this.card._on(t,"click",()=>{let r=e.querySelector("[data-role='maintenance-interval-input']");if(!r)return;let a=Number(r.dataset?.default);Number.isFinite(a)&&a>0&&(r.value=String(a))})}),e.querySelectorAll("[data-action='confirm-maintenance-reset']").forEach(t=>{this.card._on(t,"click",async()=>{let r=this.card._state.activeMaintenanceModalItem?.();if(!r||!this.card._state.canInvokeMaintenanceReset?.(r))return;if(this.card._state.setMaintenanceResetPending?.(!0),this.card._scheduleRender(),await this.card._actions.callNamedService?.(r.reset_service,r.reset_service_data)===null){let s=r.label??r.component??"item";this.card._state.setMaintenanceResetError?.(`Could not reset ${s}`),this.card.showToast?.(`Could not reset ${s}`,{kind:"error"}),this.card._scheduleRender();return}await this.card.refreshDashboardSnapshot?.();let c=String(r?.reset_kind??"").trim().toLowerCase()==="integration"?"Maintenance reset saved":"Replacement reset sent";this.card.showToast?.(c,{kind:"success"});let n=this.card._state.findUpkeepItem?.(r.kind,r.component,r.entity_id);n&&this.card._state.openMaintenanceModal?.(n),this.card._state.setMaintenanceResetSuccess?.(c),this.card._scheduleRender()})}))}}function _i(i){i._bindMetrics=function(){this.card._onAll("[data-metrics-save-profile]","click",async e=>{let t=e.currentTarget?.dataset?.metricsSaveProfile,r=e.currentTarget?.dataset?.profileKey,a=e.currentTarget?.dataset?.roomSlug;if(!t||!r)return;let c=this.card._state.findMetricsSaveCandidate?.(t,r,a),n=String(c?.save_service??"").trim(),s=c?.save_service_data;if(!c||c?.save_supported===!1||!n||!s)return;let o=this.card._state.metricsProfileSaveKey?.(t,c);this.card._state.beginMetricsProfileSave?.(o),this.card._scheduleRender();try{await this.card._actions.callNamedService?.(n,s,!0),await this.card.refreshMetricsSnapshot?.(),await this.card.refreshLearningHistorySnapshot?.()}finally{this.card._state.endMetricsProfileSave?.(),this.card._scheduleRender()}}),this.card._onAll("[data-metrics-filter-chip]","click",async e=>{let t=e.currentTarget?.dataset?.metricsFilterChip,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setMetricsFilter?.(t,r),await this.card.refreshMetricsSnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-chip-search]","input",e=>{let t=e.currentTarget,r=String(t?.value??"").toLowerCase().trim(),a=t?.closest?.("[data-chip-filter-group]");a&&a.querySelectorAll(".evcc-chip").forEach(c=>{if(c.dataset.allChip==="true"){c.style.display="";return}c.style.display=c.textContent.toLowerCase().includes(r)?"":"none"})}),this.card._onAll("[data-metrics-filter]","change",async e=>{let t=e.currentTarget?.dataset?.metricsFilter,r=e.currentTarget?.value;t&&(this.card._state.setMetricsFilter?.(t,r),await this.card.refreshMetricsSnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-metrics-tab]","click",e=>{let t=e.currentTarget?.dataset?.metricsTab;t&&(this.card._state.setMetricsActiveTab?.(t),this.card._scheduleRender())})}}function yi(i){i._orderRoot=function(){return this.card?.shadowRoot??null},i._captureOrderedRects=function(e){let t=this._orderRoot();if(!t)return new Map;let r=t.querySelectorAll(`[data-order-drop-target][data-scope="${e}"]`),a=new Map;return r.forEach(c=>{let n=c.dataset.itemId;n&&a.set(String(n),{left:c.getBoundingClientRect().left,top:c.getBoundingClientRect().top})}),a},i._applyOrderFeedback=function(e,t){let r=this._orderRoot();if(!r||t==null)return;let a=`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(t)}"]`,c=r.querySelector(a);c&&(c.classList.remove("evcc-order-feedback"),c.offsetWidth,c.classList.add("evcc-order-feedback"),window.setTimeout(()=>{c.classList.remove("evcc-order-feedback")},900))},i._playOrderFlip=function(e,t){let r=this._orderRoot();if(!r||!t?.size)return;r.querySelectorAll(`[data-order-drop-target][data-scope="${e}"]`).forEach(c=>{let n=String(c.dataset.itemId??"");if(!n||!t.has(n))return;let s=t.get(n),o=c.getBoundingClientRect(),l=s.left-o.left,d=s.top-o.top;Math.abs(l)<1&&Math.abs(d)<1||c.animate([{transform:`translate(${l}px, ${d}px)`},{transform:"translate(0px, 0px)"}],{duration:240,easing:"cubic-bezier(0.22, 1, 0.36, 1)"})})},i._runOrderMutationWithFlip=async function(e,t,r){let a=this._captureOrderedRects(e);await r()&&(this.card._scheduleRender(),await new Promise(n=>requestAnimationFrame(n)),await new Promise(n=>requestAnimationFrame(n)),this._playOrderFlip(e,a),this._applyOrderFeedback(e,t))},i.confirmOrderSelectorWithFlip=async function(){let e=this.card._state.orderSelectorScope(),t=this.card._state.orderSelectorItemId();await this._runOrderMutationWithFlip(e,t,async()=>await this.card._actions.confirmOrderedPositionChange())},i.confirmDraggedOrderWithFlip=async function(e,t){let r=this.card._state.orderDragItemId();await this._runOrderMutationWithFlip(e,r,async()=>await this.card._actions.confirmDraggedOrderChange(e,t))},i._clearDragVisualState=function(){let e=this._orderRoot();e&&(e.querySelectorAll(".evcc-order-drag-source").forEach(t=>{t.classList.remove("evcc-order-drag-source")}),e.querySelectorAll(".evcc-order-drag-target").forEach(t=>{t.classList.remove("evcc-order-drag-target")}))},i._applyDragVisualState=function(e,t,r){let a=this._orderRoot();if(a){if(this._clearDragVisualState(),t!=null){let c=a.querySelector(`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(t)}"]`);c&&c.classList.add("evcc-order-drag-source")}if(r!=null){let c=a.querySelector(`[data-order-drop-target][data-scope="${e}"][data-item-id="${String(r)}"]`);c&&c.classList.add("evcc-order-drag-target")}}},i.bindOrderEvents=function(e){e&&(this.card._on(e,"click",t=>{let r=t.target.closest("[data-action]");if(!r)return;let a=r.dataset.action;a==="open-order-selector"&&(t.preventDefault(),t.stopPropagation(),this.card._state.openOrderSelector(r.dataset.scope,r.dataset.itemId),this.card._scheduleRender()),a==="close-order-selector"&&(t.preventDefault(),this.card._state.closeOrderSelector(),this.card._scheduleRender()),a==="set-order-position"&&(t.preventDefault(),this.card._state.setOrderSelectorTargetPosition(r.dataset.position),this.card._scheduleRender()),a==="confirm-order-selector"&&(t.preventDefault(),this.confirmOrderSelectorWithFlip())}),this.card._on(e,"dragstart",t=>{let r=t.target.closest("[data-order-drag-item]");if(!r)return;let a=r.dataset.scope,c=r.dataset.itemId;if(!(!a||c==null)){this.card._state.beginOrderDrag(a,c);try{t.dataTransfer.effectAllowed="move",t.dataTransfer.setData("text/plain",String(c))}catch{}this._applyDragVisualState(a,c,c)}}),this.card._on(e,"dragover",t=>{let r=t.target.closest("[data-order-drop-target]");if(!r)return;t.preventDefault();let a=r.dataset.scope,c=r.dataset.itemId;!a||c==null||(this.card._state.setOrderDragOverItem(c),this._applyDragVisualState(a,this.card._state.orderDragItemId(),c))}),this.card._on(e,"drop",t=>{let r=t.target.closest("[data-order-drop-target]");if(!r)return;t.preventDefault();let a=r.dataset.scope,c=r.dataset.itemId;this._clearDragVisualState(),this.confirmDraggedOrderWithFlip(a,c)}),this.card._on(e,"dragend",()=>{this.card._state.clearOrderDrag(),this._clearDragVisualState()}))}}function xi(i){i._bindRunProfiles=function(){this.card._on(this.card.$("[data-action='open-new-run-profile']"),"click",()=>{this.card._state.openNewRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='cancel-run-profile-editor']"),"click",()=>{this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._onAll("[data-run-profile-field='name']","input",e=>{this.card._state.updateRunProfileDraft?.("name",e.currentTarget.value)}),this.card._onAll("[data-run-profile-field='expose_as_button']","change",e=>{this.card._state.updateRunProfileDraft?.("expose_as_button",e.currentTarget.checked),this.card._scheduleRender()}),this.card._onAll("[data-action='apply-run-profile']","click",async e=>{let t=e.currentTarget.dataset.profileId;if(!t)return;this.card._state.selectRunProfile?.(t);let r=await this.card._actions.applyRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:t});if(r?.ok===!1){alert(r.reason||"Unable to apply run profile.");return}this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),this.card._state.closeRunProfileEditor?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='save-new-run-profile']"),"click",async()=>{let e=this.card._state.runProfileDraft?.(),t=String(e?.name??"").trim();if(!t){alert("Enter a name for the run profile.");return}let r=await this.card._actions.saveRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),name:t,expose_as_button:!!e?.expose_as_button});if(r?.ok===!1){alert(r.reason||"Unable to save run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(r?.profile_id??null),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='edit-run-profile']"),"click",e=>{let t=e.currentTarget.dataset.profileId;t&&(this.card._state.selectRunProfile?.(t),this.card._state.openSelectedRunProfileEditor?.(),this.card._scheduleRender())}),this.card._on(this.card.$("[data-action='overwrite-run-profile']"),"click",async()=>{let e=this.card._state.selectedRunProfile?.(),t=this.card._state.runProfileDraft?.();if(!e)return;let r=String(t?.name??"").trim();if(!r){alert("Enter a name for the run profile.");return}let a=await this.card._actions.overwriteRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:e.id,name:r,expose_as_button:!!t?.expose_as_button});if(a?.ok===!1){alert(a.reason||"Unable to overwrite run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(e.id),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='delete-run-profile']"),"click",async e=>{let t=e.currentTarget.dataset.profileId,r=this.card._state.selectedRunProfile?.();if(!t||!r||!confirm(`Delete run profile "${r.name}"?`))return;let a=await this.card._actions.deleteRunProfile({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:this.card._state.activeMapId?.(),profile_id:t});if(a?.ok===!1){alert(a.reason||"Unable to delete run profile.");return}await this.card.refreshRunProfiles?.(),this.card._state.selectRunProfile?.(null),this.card._state.closeRunProfileEditor?.(),this.card._scheduleRender()})}}function wi(i){i._bindReview=function(){this.card._onAll("[data-review-filter-chip]","click",async e=>{let t=e.currentTarget?.dataset?.reviewFilterChip,r=e.currentTarget?.dataset?.value;if(t){if(t==="sort"){this.card._state.setLearningHistorySort?.(r),this.card._scheduleRender();return}this.card._state.setLearningHistoryFilter?.(t,r),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender()}}),this.card._onAll("[data-chip-search]","input",e=>{let t=e.currentTarget,r=String(t?.value??"").toLowerCase().trim(),a=t?.closest?.("[data-chip-filter-group]");a&&a.querySelectorAll(".evcc-chip").forEach(c=>{if(c.dataset.allChip==="true"){c.style.display="";return}c.style.display=c.textContent.toLowerCase().includes(r)?"":"none"})}),this.card._onAll("[data-review-matcher-field]","click",e=>{let t=e.currentTarget?.dataset?.reviewMatcherField,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setReviewProfileMatcherField?.(t,r),this.card._scheduleRender())}),this.card._onAll("[data-review-matcher-action]","click",e=>{e.currentTarget?.dataset?.reviewMatcherAction==="reset"&&(this.card._state.resetReviewProfileMatcher?.(),this.card._scheduleRender())}),this.card._onAll("[data-review-matcher-profile]","click",async e=>{let t=e.currentTarget?.dataset?.reviewMatcherProfile;t&&(this.card._state.setLearningHistoryFilter?.("profile_key",t),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender())}),this.card._onAll("[data-review-filter]","change",async e=>{let t=e.currentTarget?.dataset?.reviewFilter,r=e.currentTarget?.value;if(t){if(t==="sort"){this.card._state.setLearningHistorySort?.(r),this.card._scheduleRender();return}this.card._state.setLearningHistoryFilter?.(t,r),await this.card.refreshLearningHistorySnapshot?.(),this.card._scheduleRender()}}),this.card._onAll("[data-review-reason-chip]","click",e=>{let t=e.currentTarget?.dataset?.reviewReasonChip,r=e.currentTarget?.dataset?.value;t&&(this.card._state.setLearningHistoryExcludeReason?.(t,r),this.card._scheduleRender())}),this.card._onAll("[data-review-action]","click",async e=>{let t=e.currentTarget?.dataset?.reviewAction,r=e.currentTarget?.dataset?.jobId;if(!(!t||!r)){this.card._state.beginLearningHistoryJobAction?.(r),this.card._scheduleRender();try{t==="exclude"&&await this.card._actions.excludeLearningJob?.({job_id:r,reason:this.card._state.learningHistoryExcludeReason?.(r)}),t==="restore"&&await this.card._actions.restoreLearningJob?.({job_id:r}),await this.card.refreshLearningHistorySnapshot?.()}finally{this.card._state.endLearningHistoryJobAction?.(),this.card._scheduleRender()}}})}}function Si(i){i._bindRooms=function(){this._bindRoomToggles(),this._bindRoomActions(),this._bindQueueChipActions()},i._bindRoomToggles=function(){this.card._onAll("[data-room-card-toggle='true']","click",async e=>{if(e.target.closest("[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"))return;let t=e.currentTarget,r=Number(t.dataset.roomId),a=String(t.dataset.mapId),c=t.dataset.enabled==="true";!r||!a||(await this.card._actions.toggleRoomEnabled(a,r,c),c?this.card._state.disableSegmentForRoom?.(r):this.card._state.enableSegmentForRoom?.(r),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card.refreshDashboardSnapshot?.())}),this.card._onAll("[data-room-card-toggle='true']","keydown",async e=>{if(e.key!=="Enter"&&e.key!==" "||e.target.closest("[data-action='open-room-settings'], .evcc-room-settings-hit-target, [data-action='open-order-selector'], [data-order-drag-item]"))return;e.preventDefault();let t=e.currentTarget,r=Number(t.dataset.roomId),a=String(t.dataset.mapId),c=t.dataset.enabled==="true";!r||!a||(await this.card._actions.toggleRoomEnabled(a,r,c),c?this.card._state.disableSegmentForRoom?.(r):this.card._state.enableSegmentForRoom?.(r),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card.refreshDashboardSnapshot?.())})},i._bindRoomActions=function(){this.card._on(this.card.$("[data-action='primary-room-action']:not([disabled])"),"click",async()=>{if(this.card._state.cancelRunRequiresConfirmation?.()){if(this.card._state.cancelRunConfirmGuardActive?.())return;await this.card._actions.cancelActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card.showToast?.("Cancel sent \u2014 returning to dock",{kind:"info",ttl:4e3}),this.card._scheduleRender();return}if(this.card._state.hasActiveRun?.()){this.card._state.requestCancelRunConfirmation?.(),this.card._scheduleRender();return}if(this.card._state.startRequiresConfirmation?.()){await this.card._actions.startCleaning({confirmReducedRun:!0,confirmToken:this.card._state.startConfirmationToken?.()}),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender();return}await this.card._actions.startCleaning(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='cancel-primary-confirmation']"),"click",()=>{this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='pause-run']"),"click",async()=>{await this.card._actions.pauseActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='resume-run']"),"click",async()=>{await this.card._actions.resumeActiveRun(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='locate-vacuum']"),"click",async()=>{await this.card._actions.locateVacuum(),this.card.showToast?.("Locate sent \u2014 listen for the chirp",{kind:"info"}),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='select-all']"),"click",async()=>{this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card._actions.selectAllRooms(),await this.card.refreshDashboardSnapshot?.()}),this.card._on(this.card.$("[data-action='clear-queue']"),"click",async()=>{if(this.card._state.clearQueueRequiresConfirmation?.()){if(this.card._state.clearQueueConfirmGuardActive?.())return;this.card._state.clearClearQueueConfirmation?.(),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),await this.card._actions.clearQueue(),await this.card.refreshDashboardSnapshot?.(),this.card.showToast?.("Queue cleared",{kind:"success"}),this.card._scheduleRender();return}this.card._state.requestClearQueueConfirmation?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='dismiss-learning-summary']"),"click",()=>{this.card._learningController.dismissLearningSummary()}),this.card._on(this.card.$("[data-action='dismiss-incomplete-run-log']"),"click",()=>{this.card._state.clearIncompleteRunLog?.(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='queue-missed-rooms']"),"click",async()=>{let e=this.card._state.incompleteRunMissedRoomIds?.()??[],t=e.length;if(this.card._state.clearIncompleteRunLog?.(),this.card._state.clearStartConfirmation?.(),this.card._state.clearCancelRunConfirmation?.(),t===0){this.card._scheduleRender();return}let r;try{r=await this.card._actions.retryMissedRooms(e),await this.card.refreshDashboardSnapshot?.()}catch(c){console.error("[eufy-vacuum-command-center] retryMissedRooms failed",c)}let a=r!=null;this.card.showToast?.(a?`Re-queued ${t} missed room${t===1?"":"s"}`:"Could not retry missed rooms",{kind:a?"success":"error"}),this.card._scheduleRender()})},i._bindQueueChipActions=function(){let e=Array.from(this.card.shadowRoot?.querySelectorAll("[data-queue-chip='true']")??[]),t=this.card._state.queueChipLongPressMs(),r=280;e.forEach(a=>{let c=null,n=!1,s=!1,o=null;a.title="Click for settings - Double-click for estimate - Hold to remove from queue";let l=()=>{o&&(window.clearTimeout(o),o=null)},d=()=>{c&&(window.clearTimeout(c),c=null),s=!1},u=p=>{p.button!=null&&p.button!==0||(n=!1,s=!0,a.classList.add("is-pressing"),c=window.setTimeout(async()=>{if(!s)return;n=!0,l(),a.classList.remove("is-pressing"),a.classList.add("is-long-pressing");let v=Number(a.dataset.roomId),f=String(a.dataset.mapId),h=a.dataset.enabled==="true";try{await this.card._actions.toggleRoomEnabled(f,v,h),await this.card.refreshDashboardSnapshot?.()}finally{a.classList.remove("is-long-pressing")}},t))},m=()=>{a.classList.remove("is-pressing"),d()};this.card._on(a,"pointerdown",u),this.card._on(a,"pointerup",()=>{a.classList.remove("is-pressing"),d()}),this.card._on(a,"pointerleave",m),this.card._on(a,"pointercancel",m),this.card._on(a,"click",p=>{if(n){p.preventDefault(),p.stopPropagation(),n=!1,l();return}let v=Number(a.dataset.roomId),f=String(a.dataset.mapId);!v||!f||(l(),o=window.setTimeout(()=>{this.card._state.openRoomEditor(v,f),this.card._scheduleRender(),o=null},r))}),this.card._on(a,"dblclick",p=>{if(p.preventDefault(),p.stopPropagation(),n){n=!1,l();return}l();let v=Number(a.dataset.roomId),f=String(a.dataset.mapId);!v||!f||(this.card._state.openRoomEstimateModal?.(v,f),this.card._scheduleRender())}),this.card._on(a,"contextmenu",p=>{p.preventDefault()})})}}function Ri(i){i._bindRoomAccess=function(){},i._bindRoomAccessHost=function(e){if(!e)return;e.querySelectorAll("[data-action='open-room-access']").forEach(r=>{this.card._on(r,"click",a=>{a.stopPropagation();let c=r.dataset.roomId,n=r.dataset.mapId;!c||!n||(this.card._state.closeRoomEditor?.(),this.card._state.openRoomAccess?.(c,n),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='close-room-access']").forEach(r=>{this.card._on(r,"click",()=>{this.card._state.closeRoomAccess?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='toggle-is-dock-room']").forEach(r=>{this.card._on(r,"click",a=>{a.stopPropagation(),this.card._state.toggleIsDockRoomField?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='toggle-room-access-target']").forEach(r=>{this.card._on(r,"click",a=>{a.stopPropagation();let c=r.dataset.roomId;c&&(this.card._state.toggleRoomAccessTarget?.(c),this.card._scheduleRender())})});let t=e.querySelector("[data-action='save-room-access']");this.card._on(t,"click",async()=>{let r=this.card._state.activeAccessRoom?.(),a=this.card._state.roomAccessFields?.(),c=this.card._state.roomAccessValidation?.();if(!(!r||!a||!c?.valid))try{let n=await this.card._actions.saveRoomAccess?.(r.id,a.grants_access_to??[],a.is_dock_room??!1);if(n?.ok===!1||n?.updated===!1||n?.error==="invalid_access_graph"||n?.reason==="invalid_access_graph"){let s=(Array.isArray(n?.issues)&&n.issues.length?n.issues.map(o=>o?.message??String(o)).join(" "):null)??n?.reason_detail??n?.message??n?.reason??"The backend rejected this room access graph.";this.card._state.setRoomAccessSaveError?.(s),this.card._scheduleRender();return}this.card._state.closeRoomAccess?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(n){console.error("[eufy-vacuum-command-center] Failed to save room access:",n),this.card._state.setRoomAccessSaveError?.("Failed to save room access. Check Home Assistant logs for details."),this.card._scheduleRender()}})}}function Ei(i){i._bindRoomEstimate=function(){},i._bindRoomEstimateHost=function(e){e&&e.querySelectorAll("[data-action='close-room-estimate']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.closeRoomEstimateModal?.(),this.card._scheduleRender()})})}}function ki(i){i._bindRoomEditor=function(){this._bindRoomEditorOpen(),this._bindRoomEditorClose(),this._bindRoomEditorFields(),this._bindRoomEditorSave(),this._bindRoomEditorTransition()},i._refreshRoomEditorEstimates=async function(){try{await this.card._learningController?.loadRoomEstimates?.(),await this.card.refreshDashboardSnapshot?.()}catch(e){console.error("[eufy-vacuum-command-center] Failed to refresh room estimates:",e)}},i._refreshRoomProfileLibrary=async function(){try{await this.card.refreshRoomProfiles?.()}catch(e){console.error("[eufy-vacuum-command-center] Failed to refresh room profile library:",e)}},i._roomProfileTargetChoices=function(){return(this.card._state.customRoomProfiles?.()??[]).map(e=>`${e.name} (${e.label})`).join(`
`)},i._resolveEditableRoomProfileTarget=function(){let e=this.card._state.currentEditorManagedProfileName?.();if(e&&!this.card._state.isProtectedRoomProfile?.(e))return e;let t=this.card._state.customRoomProfiles?.()??[];if(!t.length)return null;let r=this._roomProfileTargetChoices(),a=window.prompt(`Choose a custom profile key:

${r}`,t[0]?.name??""),c=String(a??"").trim();if(!c)return null;let n=t.find(o=>o.name===c);return n?n.name:t.find(o=>String(o.label).toLowerCase()===c.toLowerCase())?.name??null},i._alertRoomProfileResult=function(e,t){let r=String(e?.message??e?.reason??t??"").trim();r&&window.alert(r)},i._defaultRoomProfileLabel=function(){let e=this.card._state.currentEditorManagedProfileName?.(),t=e?this.card._state.roomProfileDefinition?.(e):null,r=this.card._state.activeEditorRoom?.();return t?.label??r?.name??"Custom Room Profile"},i._openRoomEditorWithProfiles=async function(e,t){this.card._state.openRoomEditor(e,t),this.card._scheduleRender(),await this._refreshRoomProfileLibrary()},i._handleSaveRoomProfileAsNew=async function(){let e=this.card._state.activeEditorRoom?.();if(!e)return;let t=window.prompt("Save current room settings as a new profile. Enter a display label:",this._defaultRoomProfileLabel()),r=String(t??"").trim();if(!r)return;let a=this.card._state.makeRoomProfileName?.(r),c=await this.card._actions.saveRoomProfileFromRoom?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:String(e.mapId),room_id:e.id,label:r,profile_name:a});if(!c?.saved){this._alertRoomProfileResult(c,"Failed to save room profile.");return}await this._refreshRoomProfileLibrary();let n=String(c?.profile_name??a??"").trim();n&&this.card._state.applyEditorProfile?.(n),this.card._scheduleRender()},i._handleOverwriteRoomProfile=async function(){let e=this.card._state.activeEditorRoom?.();if(!e)return;let t=this._resolveEditableRoomProfileTarget();if(!t)return;let r=this.card._state.roomProfileDefinition?.(t);if(!window.confirm(`Overwrite ${r?.label??t} with this room's current settings?`))return;let c=await this.card._actions.overwriteRoomProfileFromRoom?.({vacuum_entity_id:this.card._state.vacuumEntityId?.(),map_id:String(e.mapId),room_id:e.id,profile_name:t});if(!c?.overwritten){this._alertRoomProfileResult(c,"Failed to overwrite room profile.");return}await this._refreshRoomProfileLibrary(),this.card._state.applyEditorProfile?.(t),this.card._scheduleRender()},i._handleRenameRoomProfile=async function(){let e=this._resolveEditableRoomProfileTarget();if(!e)return;let t=this.card._state.roomProfileDefinition?.(e);if(!t||this.card._state.isProtectedRoomProfile?.(e))return;let r=window.prompt("Enter the new display label for this room profile:",t.label);if(r==null)return;let a=String(r).trim();if(!a){window.alert("A room profile label is required.");return}let c=this.card._state.makeRoomProfileName?.(a,e),n=window.prompt("Optional: enter a new backend profile key.",c??e);if(n==null)return;let s=String(n).trim(),o=await this.card._actions.renameRoomProfile?.({profile_name:e,new_profile_name:s&&s!==e?s:void 0,label:a!==t.label?a:void 0});if(!o?.renamed){this._alertRoomProfileResult(o,"Failed to rename room profile.");return}await this._refreshRoomProfileLibrary();let l=this.card._state.currentEditorManagedProfileName?.(),d=String(o?.profile_name??o?.target_profile_name??e).trim();l===e&&d&&this.card._state.applyEditorProfile?.(d),this.card._scheduleRender()},i._handleDeleteRoomProfile=async function(){let e=this._resolveEditableRoomProfileTarget();if(!e)return;let t=this.card._state.roomProfileDefinition?.(e);if(!t||this.card._state.isProtectedRoomProfile?.(e)||!window.confirm(`Delete ${t.label}? This cannot be undone.`))return;let a=await this.card._actions.deleteRoomProfile?.({profile_name:e});if(!a?.deleted){this._alertRoomProfileResult(a,"Failed to delete room profile.");return}await this._refreshRoomProfileLibrary(),this.card._state._syncEditorProfileFromFields?.(),this.card._scheduleRender()},i._bindRoomEditorOpen=function(){this.card._onAll("[data-action='open-room-settings']","click",async e=>{e.stopPropagation();let t=e.currentTarget,r=t.dataset.roomId,a=t.dataset.mapId;!r||!a||await this._openRoomEditorWithProfiles(r,a)})},i._bindRoomEditorClose=function(){let e=this.card.$("[data-stop-propagation]");this.card._on(e,"click",t=>t.stopPropagation()),this.card._onAll("[data-action='close-room-editor']","click",async()=>{this.card._state.shouldSkipRefreshOnClose()?this.card._state.setSkipRefreshOnClose(!1):await this._refreshRoomEditorEstimates(),this.card._state.closeRoomEditor(),this.card._scheduleRender()})},i._bindRoomEditorFields=function(){this.card._onAll("[data-field]","click",e=>{let t=e.currentTarget,r=t.dataset.field,a=t.dataset.value;if(!(!r||a===void 0)){if(t.dataset.action==="apply-profile"){this.card._state.applyEditorProfile(a),this.card._scheduleRender();return}r==="clean_passes"&&(a=Number(a)),r==="edge_mopping"&&(a=a==="true"),this.card._state.updateEditorField(r,a),this.card._scheduleRender()}})},i._bindRoomEditorTransition=function(){this.card._onAll("[data-action='toggle-room-transition']","click",async e=>{e.stopPropagation();let t=e.currentTarget,r=t.dataset.roomId,a=t.dataset.value==="true";if(r)try{await this.card._actions.saveRoomTransition?.(r,a),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(c){console.error("[eufy-vacuum-command-center] Failed to save room transition flag:",c)}})},i._bindRoomEditorSave=function(){this.card._on(this.card.$("[data-action='save-room-editor']"),"click",async()=>{let e=this.card._state.activeEditorRoom(),t=this.card._state.editorFields();if(!(!e||!t))try{await this.card._actions.saveRoomEditor(e.mapId,e.id,t),this.card._state.setSkipRefreshOnClose(!0),await this._refreshRoomEditorEstimates(),this.card._state.closeRoomEditor(),this.card._scheduleRender()}catch(r){console.error("[eufy-vacuum-command-center] Failed to save room editor:",r)}})}}function $i(i){i._bindRoomRules=function(){let e=this.card.shadowRoot;e&&(e.querySelectorAll("[data-action='set-room-rules-tab']").forEach(t=>{this.card._on(t,"click",()=>{let r=t.dataset.roomId;r&&(this.card._state.setRoomRulesActiveRoom?.(r),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='open-new-rule']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.openNewRuleDraft?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='edit-rule']").forEach(t=>{this.card._on(t,"click",()=>{let r=t.dataset.ruleId,a=this.card._state.resolvedRoomRulesRoom?.();if(!a)return;let n=(this.card._state.roomRulesForRoom?.(a.id)??[]).find(s=>String(s.id)===String(r));n&&(this.card._state.openEditRuleDraft?.(n),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='delete-rule']").forEach(t=>{this.card._on(t,"click",async()=>{let r=t.dataset.ruleId,a=this.card._state.resolvedRoomRulesRoom?.();if(!a||!r)return;let n=(this.card._state.roomRulesForRoom?.(a.id)??[]).filter(s=>String(s.id)!==String(r));try{await this.card._actions.saveRoomRules?.(a.mapId,a.id,n),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] Failed to delete rule:",s)}})}),e.querySelectorAll("[data-action='cancel-rule-editor']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.closeRulesDraft?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-field]").forEach(t=>{this.card._on(t,"click",()=>{let r=t.dataset.ruleField,a=t.dataset.ruleValue;if(r==null)return;let c;a===""?c=null:a==="true"?c=!0:a==="false"?c=!1:r==="effect.changes.clean_passes"?c=Number(a):c=a,this.card._state.updateRuleDraftField?.(r,c),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-input]").forEach(t=>{this.card._on(t,"input",()=>{let r=t.dataset.ruleInput;r&&this.card._state.updateRuleDraftField?.(r,t.value)}),this.card._on(t,"change",()=>{this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-select]").forEach(t=>{this.card._on(t,"change",()=>{let r=t.dataset.ruleSelect;r&&(this.card._state.updateRuleDraftField?.(r,t.value||null),this.card._scheduleRender())})}),e.querySelectorAll("[data-rule-number-input]").forEach(t=>{this.card._on(t,"input",()=>{let r=t.dataset.ruleNumberInput;if(!r)return;let a=t.value;this.card._state.updateRuleDraftField?.(r,a===""?null:Number(a))}),this.card._on(t,"change",()=>{this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-multivalue]").forEach(t=>{this.card._on(t,"click",()=>{let r=String(t.dataset.ruleMultivalue??"").trim();if(!r)return;let a=this.card._state.roomRulesDraft?.(),c=Mi(a?.value),n=c.includes(r)?c.filter(s=>s!==r):[...c,r];this.card._state.updateRuleDraftField?.("value",n),this.card._scheduleRender()})}),e.querySelectorAll("[data-rule-entity-select]").forEach(t=>{this.card._on(t,"click",()=>{let r=String(t.dataset.ruleEntitySelect??"").trim();r&&(this.card._state.updateRuleDraftField?.("entity_id",r),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='save-rule']").forEach(t=>{this.card._on(t,"click",async()=>{let r=this.card._state;if(!r.roomRulesDraftIsValid?.())return;let a=r.resolvedRoomRulesRoom?.(),c=r.roomRulesDraft?.(),n=r.roomRulesDraftMode?.();if(!a||!c)return;let s=r.ruleEntityDescriptor?.(c),o=r.roomRulesForRoom?.(a.id)??[],l;n==="edit"&&c.id?l=o.map(d=>String(d.id)===String(c.id)?Ti(c,s):d):l=[...o,Ti(c,s)];try{let d=await this.card._actions.saveRoomRules?.(a.mapId,a.id,l);if(d?.ok===!1||d?.updated===!1){let u=d?.reason_detail??d?.message??d?.reason??"The backend rejected this rule.";r.setRoomRulesSaveError?.(u),this.card._scheduleRender();return}r.closeRulesDraft?.(),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender()}catch(d){console.error("[eufy-vacuum-command-center] Failed to save rule:",d),r.setRoomRulesSaveError?.("Failed to save rule. Check Home Assistant logs."),this.card._scheduleRender()}})}))}}function Ti(i,e){let t={entity_id:String(i.entity_id??"").trim(),kind:i.kind??"blocker",operator:i.operator??"is_on",enabled:i.enabled!==!1,effect:{action:i.kind==="modifier"?"mutate":"exclude",reason:String(i.effect?.reason??"").trim()||null}};if(i.id&&(t.id=i.id),i.label?.trim()&&(t.label=i.label.trim()),!Yn.has(t.operator)&&i.value!=null){let r=Kn(i.value,e,t.operator);(Array.isArray(r)?r.length:String(r).trim())&&(t.value=r)}if(i.kind==="modifier"){let r=i.effect?.changes??{},a={};for(let[s,o]of Object.entries(r))if(o!=null){if(s==="clean_passes"){let l=Number(o);(l===1||l===2)&&(a[s]=l);continue}a[s]=o}t.effect.changes=a;let n=(Array.isArray(i.fan_out_room_ids)?i.fan_out_room_ids:[]).map(Number).filter(s=>Number.isFinite(s)&&s>0);n.length&&(t.fan_out_room_ids=n)}return t}function Kn(i,e,t){let r=e?.valueModeForOperator?.(t)??"text";if(r==="multi-select")return Mi(i);if(r==="number"){let a=Number(i);return Number.isFinite(a)?a:i}return i}function Mi(i){if(Array.isArray(i))return i.map(t=>String(t??"").trim()).filter(Boolean);let e=String(i??"").trim();return e?e.split(",").map(t=>t.trim()).filter(Boolean):[]}var Yn=new Set(["is_on","is_off","exists","missing"]);var Mt=`

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
`,Ai=`

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
    --evcc-surface-subtle: rgba(255,255,255,0.04);
    --evcc-surface-chip:   rgba(255,255,255,0.09);
    --evcc-surface-action: rgba(255,255,255,0.10);
    --evcc-surface-action-hover: rgba(255,255,255,0.18);
    --evcc-surface-sunken: rgba(0,0,0,0.18);
    --evcc-surface-warning: rgba(255,180,0,0.12);

    /* Text */
    --evcc-text-primary:   var(--primary-text-color, #f0f2f5);
    --evcc-text-secondary: var(--secondary-text-color, rgba(240,242,245,0.72));
    --evcc-text-muted:     rgba(240,242,245,0.48);
    --evcc-text-strong:    var(--primary-text-color, #f0f2f5);
    --evcc-text-on-accent: #ffffff;

    /* Borders */
    --evcc-border-subtle:  rgba(255,255,255,0.06);
    --evcc-border-default: rgba(255,255,255,0.10);
    --evcc-border-strong:  rgba(255,255,255,0.18);
    --evcc-border-warning: rgba(255,180,0,0.35);

    /* Accent */
    --evcc-accent: var(--accent-color, #3b82f6);
    --evcc-accent-soft: rgba(0,229,255,0.16);

    /* Generic semantics */
    --evcc-sem-success: var(--success-color, #4caf6e);
    --evcc-sem-warning: var(--warning-color, #f5a623);
    --evcc-sem-error:   var(--error-color,   #e05252);
    /* Info: a stable literal blue, NOT var(--info-color, \u2026) \u2014 HA's
       --info-color is theme-inconsistent (amber in some themes) and could
       collide with the warning hue. Used for reference/baseline states. */
    --evcc-sem-info:    #4a9fe0;

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
    --evcc-bg-input:      var(--evcc-surface-input);

    /* Old status colors \u2192 mapped to semantics */
    --evcc-color-cleaning:  var(--evcc-sem-success);
    --evcc-color-docked:    var(--evcc-accent);
    --evcc-color-error:     var(--evcc-sem-error);
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

  ${Mt}
`;var Ci=`
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
`;var Ii=`
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
    /* Long suggested-profile names must wrap inside the narrow card, not clip. */
    white-space: normal;
    height: auto;
    min-height: 0;
    line-height: 1.3;
    text-align: center;
    overflow-wrap: anywhere;
    max-width: 100%;
  }

  .evcc-metrics-card-title {
    min-width: 0;
    overflow-wrap: anywhere;
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

  /* Searchable profile filter: label + search input on one row, then a
     height-capped, scrollable chip area so a long profile list never walls the
     panel. Shared by the Metrics and Learning Review filters. */
  .evcc-chip-filter-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .evcc-chip-filter-head .evcc-field-label {
    margin: 0;
    flex: 0 0 auto;
  }

  .evcc-chip-search {
    flex: 1 1 auto;
    min-width: 0;
    height: 28px;
    padding: 0 10px;
    font-family: inherit;
    font-size: 0.8rem;
    color: var(--evcc-text-primary);
    background: var(--evcc-surface-input);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px);
    outline: none;
  }

  .evcc-chip-search:focus {
    border-color: var(--evcc-accent, var(--evcc-border-strong));
  }

  .evcc-chip-filter--searchable .evcc-metrics-filter-chips,
  .evcc-chip-filter--searchable .evcc-review-filter-chips {
    max-height: 132px;
    overflow-y: auto;
    padding-right: 2px;
  }

  /* Long disambiguated labels wrap inside the chip (like the card badges) so the
     group only ever scrolls vertically, never overflows its column width. */
  .evcc-chip-filter--searchable .evcc-chip {
    white-space: normal;
    height: auto;
    line-height: 1.25;
    text-align: center;
    overflow-wrap: anywhere;
    max-width: 100%;
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
    background: var(--evcc-surface-sunken, rgba(0, 0, 0, 0.18));
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 10px 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
    color: var(--evcc-text-primary);
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
`;var Oi=`
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
`;var Li=`

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

  .evcc-dock-status {
    margin-top: 2px;
  }

  .evcc-status-prefix {
    color:        var(--evcc-text-muted);
    margin-right: 4px;
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

  /* =========================================================
     TOASTS
     =========================================================
     Floating stack of transient feedback pills. Pinned to the
     bottom of the card so it sits above the mobile bottom nav
     and the view content. Pointer-events: none on the root so
     the toasts don't intercept clicks behind them; the
     individual toast re-enables them for the dismiss button.
     ========================================================= */

  .evcc-toast-root {
    position:       absolute;
    left:           0;
    right:          0;
    bottom:         16px;
    display:        flex;
    justify-content: center;
    pointer-events: none;
    z-index:        50;
  }

  .evcc-toast-stack {
    display:        flex;
    flex-direction: column-reverse;
    gap:            8px;
    align-items:    center;
    max-width:      90%;
    pointer-events: none;
  }

  .evcc-toast {
    pointer-events: auto;
    display:        flex;
    align-items:    center;
    gap:            10px;
    padding:        8px 12px;
    border-radius:  10px;
    font-size:      0.85rem;
    background:     var(--evcc-surface-raised, rgba(30, 30, 30, 0.94));
    color:          var(--evcc-text-primary);
    box-shadow:     0 4px 14px rgba(0, 0, 0, 0.28);
    border:         1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
    min-width:      200px;
    max-width:      420px;
    animation:      evcc-toast-in 160ms ease-out;
  }

  .evcc-toast--success {
    border-left: 3px solid var(--evcc-sem-success);
  }

  .evcc-toast--error {
    border-left: 3px solid var(--evcc-sem-error);
  }

  .evcc-toast--info {
    border-left: 3px solid var(--evcc-accent);
  }

  .evcc-toast-message {
    flex: 1;
    line-height: 1.3;
  }

  .evcc-toast-dismiss {
    background:   transparent;
    border:       none;
    color:        var(--evcc-text-muted);
    cursor:       pointer;
    font-size:    0.95rem;
    padding:      0 4px;
    line-height:  1;
  }

  .evcc-toast-dismiss:hover {
    color: var(--evcc-text-primary);
  }

  @keyframes evcc-toast-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .evcc-shell {
    position: relative;
  }
`;var Pi=`

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
`;var Ni=`

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

`;var Fi=`

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

  /* Inline banner shown while the cancel-run two-tap confirmation
     is in flight. Pairs with the pulsing "Confirm Cancel" chip. */
  .evcc-rooms-cancel-warning {
    margin-top: 6px;
    padding: 8px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error, #ef4444) 38%, transparent);
    color: var(--evcc-text-primary);
    font-size: 0.82rem;
    line-height: 1.35;
  }

  /* Non-blocking caution: a tank-driven mop will wet-drag carpet (Roborock S6
     with the water tank attached + a carpet room in the run). */
  .evcc-rooms-carpet-warning {
    margin-top: 6px;
    padding: 8px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    background: color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 40%, transparent);
    color: var(--evcc-text-primary);
    font-size: 0.82rem;
    line-height: 1.35;
  }

  /* Informational (not an alert): order is advisory on path-optimizing brands. */
  .evcc-rooms-order-advisory {
    margin-top: 6px;
    padding: 7px 10px;
    border-radius: var(--evcc-radius-inner, 8px);
    background: color-mix(in srgb, var(--evcc-text-muted) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-text-muted) 20%, transparent);
    color: var(--evcc-text-muted);
    font-size: 0.78rem;
    line-height: 1.4;
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
    isolation:       isolate;   /* stacking context: lets the texture sit at z-index:-1, beneath the progress fill */
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
     FLOOR-TEXTURE LEGIBILITY
     ---------------------------------------------------------
     The floor texture is a variable-luminance layer painted
     BEHIND card content. The status / setting chips and the room
     name are translucent (they rely on the dark card showing
     through), so over a bright or same-hue texture they lose
     contrast \u2014 red on gold, amber on pale marble, the white name
     on a light floor, the muted "ago" chip on anything light.
     CSS cannot sample an image's luminance to pick a contrasting
     color, so rather than tune any single color we composite each
     chip OVER AN OPAQUE SURFACE: legibility becomes independent of
     whatever texture sits behind \u2014 for any chip color and any
     floor. Texture stays fully visible everywhere else.
     ========================================================= */

  /* Token-system chips (mode pills + status): their tint is a
     background-COLOR, so re-emit it as an image layer stacked on
     top of an opaque surface base (hue/intensity unchanged). */
  .evcc-room-card .evcc-room-status,
  .evcc-room-card .evcc-room-setting-chip {
    background:
      linear-gradient(
        var(--evcc-chip-bg, var(--evcc-surface-input)),
        var(--evcc-chip-bg, var(--evcc-surface-input))
      ),
      var(--evcc-surface-card);
  }

  /* Confidence chips: their tint is already a gradient IMAGE, so
     an opaque background-color beneath it is enough (the variant
     gradient still renders on top). */
  .evcc-room-card .evcc-learning-chip {
    background-color: var(--evcc-surface-card);
  }

  /* Action-row controls (Move / drag handle / settings gear) are .evcc-chip with
     a translucent resting bg, so they vanish on a light texture. Give them the
     same opaque surface backing. Hover/active already resolve to opaque surfaces
     (surface-panel / accent), so only the resting state needs this. */
  .evcc-room-card .evcc-chip {
    background:
      linear-gradient(
        var(--evcc-chip-bg, var(--evcc-surface-input)),
        var(--evcc-chip-bg, var(--evcc-surface-input))
      ),
      var(--evcc-surface-card);
  }

  /* Bare text \u2014 order number (#N) + room name \u2014 gets a surface-colored halo so
     the text survives a map texture behind the card. The halo is the card's own
     surface colour, so it self-outlines correctly on both light and dark themes. */
  .evcc-room-card .evcc-order-chip,
  .evcc-room-card .evcc-room-name {
    text-shadow:
      0 0 2px var(--evcc-surface-card),
      0 1px 3px var(--evcc-surface-card),
      0 0 6px var(--evcc-surface-card);
  }

  /* The order number (#N) is a secondary label, not the room name. Bind it to a
     theme text token \u2014 it previously inherited a fixed pale colour that vanished
     on light themes (the room name sets --evcc-text-primary explicitly; #N did
     not, so it fell through to a near-white cascade value). */
  .evcc-room-card .evcc-order-chip {
    color: var(--evcc-text-secondary);
  }

  /* Estimate notes (e.g. the warning-variant "intensity mismatch") are bare
     colored text \u2014 back them as self-hugging pills so the tint reads on any
     texture (rare notes that weren't on screen for the first pass). */
  .evcc-room-card .evcc-room-note {
    align-self:       flex-start;
    padding:          2px 8px;
    border-radius:    var(--evcc-radius-chip, 999px);
    background-color: var(--evcc-surface-card);
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

  /* "Last cleaned ~Nd ago" pill, sourced from room_history. */
  .evcc-room-status--last-cleaned {
    color: var(--evcc-text-muted);
    background: var(--evcc-surface-subtle, rgba(255, 255, 255, 0.04));
    border-color: var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
    opacity: 0.85;
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

  /* Live anomaly states. skipped = the queue advanced past an un-cleaned room
     (dashed warning + struck-through label); running-long = an additive warning ring
     on the current chip when it overruns its estimate (below the 2x stall). */
  .evcc-queue-chip--skipped {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 45%, transparent);
    border-style: dashed;
    opacity: 0.7;
  }
  .evcc-queue-chip--skipped .evcc-queue-chip-label {
    text-decoration: line-through;
  }
  .evcc-queue-chip--running-long {
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 60%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
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
`;var At=`
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
`;var Ct=`
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
`;var Di=`

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

/* Rule fan-out badge on the rule card \u2014 small "\u2192 also affects N rooms"
   line under the effect summary so users can spot fan-out rules in the
   list without opening the editor. */
.evcc-rule-fan-out {
  font-size:    0.74rem;
  color:        var(--evcc-accent, #60a5fa);
  margin-top:   2px;
}

.evcc-rule-disabled-tag {
  flex-shrink:   0;
  align-self:    center;
  padding:       2px 7px;
  border-radius: 999px;
  font-size:     0.68rem;
  font-weight:   600;
  background:    var(--evcc-surface-input, rgba(255,255,255,0.06));
  color:         var(--evcc-text-muted, rgba(240,242,245,0.48));
  border:        1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
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
`;var Hi=`
  .evcc-rooms-workspace {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: start;
  }

  .evcc-rooms-main {
    flex: 2 1 380px;
    min-width: 0;
  }

  .evcc-run-profiles-panel {
    flex: 1 1 300px;
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

  /* Responsive collapse is handled by flex-wrap above (container-relative) \u2014
     NOT a viewport @media query. The card can be narrower than the screen
     (HA panel, dashboard column, render harness), so a viewport breakpoint
     would leave the 320px panel overlapping the rooms on a wide screen. */
`;var It=`
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
`,zi=`
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

  /* Derived "Due in ~N days" projection. Card-side calc from
     used_since_reset_hours / days_since_reset \u2192 hours_per_day. */
  .evcc-maintenance-card-due {
    display: inline-block;
    align-self: flex-start;
    margin-top: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.74rem;
    color: var(--evcc-text-secondary);
    background: var(--evcc-surface-subtle, rgba(255,255,255,0.06));
    border: 1px solid var(--evcc-border-subtle, rgba(255,255,255,0.08));
  }

  .evcc-maintenance-modal-hero-due {
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--evcc-text-secondary);
    opacity: 0.9;
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

  ${It}

  @media (max-width: 720px) {
    .evcc-maintenance-grid {
      grid-template-columns: 1fr;
    }

    .evcc-maintenance-stats {
      grid-template-columns: 1fr;
    }
  }
`;var Bi=`

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

  /* Read-only mop-state indicator (tank-driven brands, e.g. Roborock). */
  .evcc-room-editor-mopstate {
    padding:       8px 11px;
    border-radius: 8px;
    font-size:     0.82rem;
    font-weight:   600;
    line-height:   1.3;
  }

  .evcc-room-editor-mopstate.mopping {
    background: color-mix(in srgb, var(--evcc-accent, #3b9eff) 16%, transparent);
    border:    1px solid color-mix(in srgb, var(--evcc-accent, #3b9eff) 34%, transparent);
    color:     var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-room-editor-mopstate.vacuum {
    background: color-mix(in srgb, var(--evcc-text-muted) 10%, transparent);
    border:    1px solid color-mix(in srgb, var(--evcc-text-muted) 22%, transparent);
    color:     var(--evcc-text-muted);
  }

  /* Muted helper note under a field (e.g. whole-run passes on Roborock). */
  .evcc-room-editor-field-note {
    margin-top:  6px;
    color:       var(--evcc-text-muted);
    font-size:   0.74rem;
    line-height: 1.4;
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
`;var ji=`

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
`;var Vi=`
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
     THEME MODE (follow system vs this device only)
     ========================================================= */

  .evcc-theme-mode {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    flex: none;
  }

  .evcc-theme-mode-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-theme-mode-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    margin-right: 2px;
  }

  .evcc-theme-mode-detail {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--evcc-radius-inner, 10px);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-accent, #3b82f6) 30%, transparent);
  }

  .evcc-theme-mode-state {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 18px;
    font-size: 0.85rem;
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-theme-mode-state .k {
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-right: 5px;
  }

  .evcc-theme-mode-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .evcc-theme-mode-note {
    margin: 0;
    font-size: 0.78rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
  }

  /* =========================================================
     PRESET (THEME) FACET FILTER + SEARCH
     ========================================================= */

  .evcc-preset-filters {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 10px;
    flex: none; /* fixed band; the grid below scrolls */
  }

  /* The theme grid scrolls so every preset is reachable under the fixed filter
     band (the view-content itself is overflow:hidden, like the token editor). */
  .evcc-preset-scroll {
    flex: 1 1 auto;
    height: 0;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
    padding-right: 4px;
  }

  .evcc-preset-filters-top {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .evcc-preset-filters-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    text-transform: none;
  }

  .evcc-preset-filters-toggle ha-icon {
    --mdc-icon-size: 15px;
  }

  .evcc-preset-filters-caret {
    transition: transform 150ms ease;
  }

  .evcc-preset-filters-toggle.active .evcc-preset-filters-caret {
    transform: rotate(180deg);
  }

  .evcc-preset-search {
    flex: 1;
    min-width: 160px;
    height: 34px;
  }

  .evcc-preset-clear {
    flex-shrink: 0;
  }

  .evcc-preset-gallery-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-left: auto;
    flex-shrink: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--evcc-accent, #3b82f6);
    text-decoration: none;
    padding: 6px 10px;
    border-radius: var(--evcc-radius-inner, 10px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    transition: var(--evcc-transition-normal, 150ms ease);
    white-space: nowrap;
  }

  .evcc-preset-gallery-link:hover {
    border-color: var(--evcc-accent, #3b82f6);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
  }

  .evcc-preset-gallery-link ha-icon {
    --mdc-icon-size: 15px;
  }

  .evcc-preset-facets {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .evcc-preset-facet {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
  }

  .evcc-preset-facet-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    width: 64px;
    flex: none;
  }

  .evcc-preset-facet-chip {
    text-transform: capitalize;
    font-size: 0.74rem;
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

  .evcc-preset-tags {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 4px;
  }

  .evcc-preset-tag {
    font-size: 0.62rem;
    line-height: 1;
    padding: 3px 6px;
    border-radius: 999px;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    white-space: nowrap;
  }

  /* colorblind-safe is system-verified \u2014 tint it with the success semantic. */
  .evcc-preset-tag[data-facet="a11y"] {
    color: var(--evcc-sem-success, #4caf6e);
    border-color: color-mix(in srgb, var(--evcc-sem-success, #4caf6e) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-success, #4caf6e) 12%, transparent);
  }

  .evcc-preset-tag[data-facet="source"] {
    color: var(--evcc-accent, #3b82f6);
    border-color: color-mix(in srgb, var(--evcc-accent, #3b82f6) 45%, transparent);
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
  }

  /* --- Inline vibe-tag editor --- */
  .evcc-preset-tag-edit {
    position: absolute;
    top: 6px;
    left: 6px;
    z-index: 2;
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.6));
    cursor: pointer;
    padding: 2px;
    opacity: 0.65;
    --mdc-icon-size: 16px;
  }

  .evcc-preset-tag-edit:hover,
  .evcc-preset-tag-edit.active {
    color: var(--evcc-accent, #3b82f6);
    opacity: 1;
  }

  .evcc-preset-card.editing {
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-preset-tag-editor {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 2px;
    padding-top: 6px;
    border-top: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
  }

  .evcc-preset-vibe-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .evcc-preset-vibe-chip {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-size: 0.66rem;
    line-height: 1;
    padding: 3px 4px 3px 7px;
    border-radius: 999px;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
  }

  .evcc-preset-vibe-remove {
    border: none;
    background: none;
    color: var(--evcc-text-muted, rgba(255, 255, 255, 0.5));
    cursor: pointer;
    font-size: 0.85rem;
    line-height: 1;
    padding: 0 1px;
  }

  .evcc-preset-vibe-remove:hover {
    color: var(--evcc-sem-error, #e05252);
  }

  .evcc-preset-tag-add {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .evcc-preset-tag-input {
    flex: 1;
    min-width: 0;
    font: inherit;
    font-size: 0.72rem;
    padding: 4px 7px;
    border-radius: var(--evcc-radius-inner, 8px);
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.05));
    color: var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-preset-tag-input:focus {
    outline: none;
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-preset-tag-done {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.1));
    background: none;
    color: var(--evcc-accent, #3b82f6);
    border-radius: var(--evcc-radius-inner, 8px);
    cursor: pointer;
    padding: 3px;
    --mdc-icon-size: 16px;
  }

  .evcc-preset-tag-done:hover {
    background: color-mix(in srgb, var(--evcc-accent, #3b82f6) 12%, transparent);
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
`;var qi=`
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

  /* ------------------------------------------------------------------
     Animal Companion preview grid
     ------------------------------------------------------------------
     5 battery-state rows \xD7 N animal columns. Each cell is a thumbnail
     <animal-svg>. The grid inherits the card's draft theme tokens via
     CSS custom-property cascade \u2014 no JS wiring needed to make the
     previews react to token edits.
  ----------------------------------------------------------------- */
  .evcc-theme-preview-animal-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--evcc-surface-panel, var(--evcc-panel-bg, #1c2127));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    border-radius: var(--evcc-radius-card, 16px);
    padding: 14px;
  }

  .evcc-theme-preview-animal-row {
    display: grid;
    grid-template-columns: 90px repeat(auto-fit, minmax(80px, 1fr));
    align-items: center;
    gap: 8px;
  }

  /* Single-animal (sub-group) preview: one larger cell, centred. */
  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-row {
    grid-template-columns: 90px 1fr;
  }

  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-cell {
    min-height: 110px;
    padding: 8px;
  }

  .evcc-theme-preview-animal-grid--single .evcc-theme-preview-animal-collabel {
    text-align: left;
    padding-left: 8px;
  }

  .evcc-theme-preview-animal-row--header {
    border-bottom: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    padding-bottom: 6px;
    margin-bottom: 2px;
  }

  .evcc-theme-preview-animal-rowlabel {
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-size: 12px;
    color: var(--evcc-text-primary, #e6e6e6);
  }

  .evcc-theme-preview-animal-rowlabel-title {
    font-weight: 600;
  }

  .evcc-theme-preview-animal-rowlabel-hint {
    font-size: 10px;
    color: var(--evcc-text-muted, #9ca3af);
  }

  .evcc-theme-preview-animal-collabel {
    font-size: 11px;
    text-align: center;
    text-transform: capitalize;
    color: var(--evcc-text-secondary, #c7c9d1);
  }

  .evcc-theme-preview-animal-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    background: var(--evcc-surface-subtle, rgba(255, 255, 255, 0.03));
    border-radius: 8px;
    min-height: 60px;
  }

  .evcc-theme-preview-animal-note {
    font-size: 11px;
    line-height: 1.45;
    color: var(--evcc-text-muted, #9ca3af);
    margin-top: 8px;
  }

  .evcc-theme-preview-animal-note code {
    background: var(--evcc-surface-subtle, rgba(255, 255, 255, 0.06));
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10.5px;
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
`;var Gi=`

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

  /* =========================================================
     ZOOM TOOLBAR
     =========================================================
     Floating control bar pinned to the bottom-right of the
     map container. Sits above all other map layers; pointer
     events enabled so the buttons are clickable. The buttons
     drive state.applyMapZoom / state.resetMapTransform; the
     readout reflects state.mapZoom() as a percentage.
     ========================================================= */

  .evcc-map-zoom-toolbar {
    position:        absolute;
    right:           10px;
    bottom:          10px;
    display:         flex;
    align-items:     center;
    gap:             4px;
    padding:         4px 6px;
    background:      var(--evcc-map-tooltip-bg, rgba(20, 30, 50, 0.85));
    border:          1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
    border-radius:   6px;
    backdrop-filter: blur(4px);
    z-index:         10;
    pointer-events:  auto;
    user-select:     none;
  }

  .evcc-map-zoom-btn {
    width:           28px;
    height:          28px;
    line-height:     1;
    font-size:       16px;
    font-weight:     600;
    color:           var(--evcc-map-tooltip-text, #fff);
    background:      var(--evcc-surface-action, rgba(255, 255, 255, 0.08));
    border:          1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.15));
    border-radius:   4px;
    cursor:          pointer;
    display:         flex;
    align-items:     center;
    justify-content: center;
    transition:      background-color 0.15s ease, transform 0.05s ease;
  }
  .evcc-map-zoom-btn:hover {
    background:      var(--evcc-surface-action-hover, rgba(255, 255, 255, 0.18));
  }
  .evcc-map-zoom-btn:active {
    transform:       scale(0.93);
  }

  .evcc-map-zoom-readout {
    min-width:       42px;
    text-align:      center;
    font-size:       12px;
    color:           var(--evcc-map-tooltip-hint, rgba(255, 255, 255, 0.7));
    padding:         0 2px;
    font-variant-numeric: tabular-nums;
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
    font-size:     0.82rem;
    font-weight:   700;
    color:         var(--evcc-map-label-text, #ffffff);
    /* Subtle dark pill behind the text: nearly invisible on the dark CV map
       (dark-on-dark), but a consistent bed for white text on light / photo
       custom backdrops (e.g. a near-white sky over green foliage). Both the
       background (alpha is the legibility knob) and the text colour are theme
       tokens \u2014 tune them in the Theme editor's "Map" group. The tight casing
       keeps edges crisp over busy mid-tones. */
    background:    var(--evcc-map-label-bg, rgba(15, 18, 22, 0.60));
    padding:       1px 7px;
    border-radius: 7px;
    text-shadow:   0 0 2px rgba(0, 0, 0, 0.85);
    white-space:   nowrap;
    line-height:   1.25;
    text-align:    center;
  }

  .evcc-map-label--selected .evcc-map-label-name {
    color: var(--evcc-map-label-text-selected, #ffffff);
  }

  .evcc-map-label-order {
    display:         flex;
    align-items:     center;
    justify-content: center;
    width:           16px;
    height:          16px;
    border-radius:   50%;
    background:      var(--evcc-accent, #3b82f6);
    color:           var(--evcc-map-label-order-text, #fff);
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
    background:     var(--evcc-map-tooltip-bg, rgba(15, 18, 22, 0.88));
    backdrop-filter: blur(6px);
    border:         1px solid var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));
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
    color:       var(--evcc-map-tooltip-text, #f0f2f5);
    white-space: nowrap;
  }

  .evcc-map-tooltip-hint {
    font-size: 0.72rem;
    color:     var(--evcc-map-tooltip-hint, rgba(240, 242, 245, 0.55));
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
    color:           var(--evcc-map-label-order-text, #fff);
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
    filter: drop-shadow(0 0 1px var(--evcc-map-vertex-selected-glow, rgba(255, 221, 0, 0.9)));
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

  /* CV / Custom layout picker (segmented control; wraps with many layouts) */
  .evcc-map-mode-toggle {
    display:   flex;
    flex-wrap: wrap;
    gap:       6px;
  }

  /* Layout-name input (create / rename a custom layout) */
  .evcc-map-config-input {
    flex:          1 1 8rem;
    min-width:     0;
    padding:       5px 9px;
    border-radius: 7px;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.14));
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    color:         var(--evcc-text-primary, #eef1f5);
    font-size:     0.82rem;
  }

  .evcc-map-mode-btn {
    flex:          1;
    padding:       7px 10px;
    border-radius: 8px;
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    background:    var(--evcc-surface-raised, rgba(255, 255, 255, 0.04));
    color:        var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    font-size:     0.82rem;
    font-weight:   600;
    cursor:        pointer;
    transition:    background 0.15s, border-color 0.15s, color 0.15s;
  }

  .evcc-map-mode-btn:hover {
    border-color: var(--evcc-accent, #00e5ff);
  }

  .evcc-map-mode-btn--active {
    background:   var(--evcc-accent-soft, rgba(0, 229, 255, 0.14));
    border-color: var(--evcc-accent, #00e5ff);
    color:        var(--evcc-text-primary, #f0f2f5);
  }

  /* Custom-segment composer */
  .evcc-compose-tools {
    display: flex;
    gap:     6px;
  }

  .evcc-compose-shape {
    /* Stroke uses --evcc-grp (injected only on merged groups) so shapes that
       share a room share an outline colour; un-merged shapes keep the accent. */
    fill:           var(--evcc-accent-soft, rgba(0, 229, 255, 0.16));
    stroke:         var(--evcc-grp, var(--evcc-accent, #00e5ff));
    stroke-width:   0.5;
    cursor:         pointer;
    pointer-events: all;
  }

  .evcc-compose-shape--selected {
    fill:          var(--evcc-accent-soft, rgba(0, 229, 255, 0.30));
    stroke:        var(--evcc-map-compose-selected-stroke, #ffffff);
    stroke-width:  3;
    vector-effect: non-scaling-stroke;
  }

  /* Black halo drawn under .evcc-compose-shape--selected (emitted as a sibling in
     map.js renderer). 5px non-scaling under the 3px selection stroke leaves 1px of
     black on each side, so the bright outline survives a light custom-photo backdrop
     (black reads on light) while the bright core still reads on a dark CV map. */
  .evcc-compose-shape-halo {
    fill:           none;
    stroke:         #000;
    stroke-width:   5;
    vector-effect:  non-scaling-stroke;
    pointer-events: none;
  }

  /* Cutout: this shape carves a hole out of its merged room. Dashed + a warning
     tint so it reads as "subtracted" rather than filled. */
  .evcc-compose-shape--cut {
    fill:             var(--evcc-map-compose-cut-fill, rgba(255, 92, 92, 0.12));
    stroke-dasharray: 2 1.4;
  }
  .evcc-compose-shape--cut.evcc-compose-shape--selected {
    fill: var(--evcc-map-compose-cut-selected-fill, rgba(255, 92, 92, 0.20));
  }

  /* Custom backdrop fills the square exactly like the 0-100 draw grid, so a
     traced shape lines up with the picture (CV maps stay object-fit: contain). */
  .evcc-map-image--fill {
    object-fit: fill;
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

  /* Per-variant delete button \u2014 flatter, error-tinted treatment to
     keep the primary Upload button as the visual anchor of the row. */
  .evcc-map-config-btn--danger {
    background: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 12%, transparent);
    color:      var(--evcc-sem-error, #ef4444);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 36%, transparent);
  }

  .evcc-map-config-btn--danger:hover {
    background:   color-mix(in srgb, var(--evcc-sem-error, #ef4444) 22%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-error, #ef4444) 56%, transparent);
  }

  /* Armed (second-click) state for the per-variant delete button.
     Solid error fill + pulse so the user can't mistake it for a
     primary action chip. Auto-clears after 5s (see bindings/map.js). */
  .evcc-map-config-btn--confirm {
    background:   var(--evcc-sem-error, #ef4444);
    color:        var(--evcc-text-on-accent, #fff);
    border-color: var(--evcc-sem-error, #ef4444);
    font-weight:  700;
    animation:    evcc-variant-delete-pulse 1.1s ease-in-out infinite;
  }

  @keyframes evcc-variant-delete-pulse {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--evcc-sem-error, #ef4444) 55%, transparent); }
    50%      { box-shadow: 0 0 0 6px color-mix(in srgb, var(--evcc-sem-error, #ef4444) 0%, transparent); }
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
`;var Ui=`

  /* =========================================================
     CARD TEXTURE CONTAINER
     ========================================================= */

  .evcc-room-texture-layer {
    position:       absolute;
    inset:          0;
    pointer-events: none;
    z-index:        0;
  }

  /* Texture sits at the very bottom of the card's content. The card uses
     isolation:isolate to form a stacking context, so z-index:-1 keeps the
     texture ABOVE the card background but BENEATH the queue progress fill
     (::before, z-index:0) and the pulse (::after) and all content
     (.evcc-room-card > *, z-index:1). At z-index:0 the texture \u2014 a sibling
     painted later in tree order \u2014 would occlude the ::before progress fill.
     This higher-specificity rule also overrides the card > * z-index:1 rule. */
  .evcc-room-card > .evcc-room-texture-layer {
    position: absolute;
    z-index:  -1;
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

  /* Optional per-layer blur wrapper. Wraps a masked layer so the blur lands
     AFTER masking (CSS does filter before mask), softening the layer's edges
     rather than blurring a flat fill that then gets hard-clipped. */
  .evcc-ftx-blur {
    display:        block;
    position:       absolute;
    inset:          0;
    pointer-events: none;
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
`;var Wi=`
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
    background:     var(--evcc-surface-sunken, rgba(0, 0, 0, 0.18));
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

  /* =========================================================
     ROOM DRIFT PANEL \u2014 new / removed / transiently-missing rooms
     surfaced inside the save_rooms step when discovery shows
     the integration is out of sync with the vacuum's segments.
     ========================================================= */

  .evcc-setup-drift-panel {
    display:        flex;
    flex-direction: column;
    gap:            12px;
    margin-top:     12px;
    margin-bottom:  8px;
  }

  .evcc-setup-drift-section {
    border-radius: 8px;
    border:        1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));
    background:    var(--evcc-surface-subtle, rgba(255, 255, 255, 0.03));
    padding:       12px 14px;
    display:       flex;
    flex-direction: column;
    gap:           8px;
  }

  /* Section colour-coding mirrors the semantic meaning of each
     drift category \u2014 new rooms are an info/action prompt, removed
     rooms are warning-coloured because user action just lost data,
     transient is muted because no action is needed yet. */
  .evcc-setup-drift-section.new {
    border-color: color-mix(in srgb, var(--evcc-sem-info, #38bdf8) 35%, transparent);
  }
  .evcc-setup-drift-section.removed {
    border-color: color-mix(in srgb, var(--evcc-sem-warning, #fbbf24) 40%, transparent);
  }
  .evcc-setup-drift-section.transient {
    border-color: color-mix(in srgb, var(--evcc-text-muted, #94a3b8) 30%, transparent);
    opacity:      0.92;
  }

  .evcc-setup-drift-title {
    font-size:   0.92rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-drift-hint {
    font-size: 0.8rem;
    color:     var(--evcc-text-muted, #94a3b8);
    line-height: 1.4;
  }

  .evcc-setup-drift-list {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    margin-top:     4px;
  }

  .evcc-setup-drift-row {
    display:         flex;
    align-items:     center;
    gap:             10px;
    padding:         6px 10px;
    border-radius:   6px;
    background:      var(--evcc-surface-subtle, rgba(255, 255, 255, 0.04));
  }

  .evcc-setup-drift-room-name {
    flex:        1 1 auto;
    font-size:   0.88rem;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-drift-room-map {
    font-size: 0.75rem;
    margin-right: 8px;
  }

  /* =========================================================
     PANEL RENAME
     ========================================================= */

  .evcc-setup-rename {
    display:        flex;
    flex-direction: column;
    gap:            8px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-rename-title {
    font-size:   0.95rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-rename-row {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .evcc-setup-rename-input {
    flex:          1 1 auto;
    min-width:     0;
    padding:       8px 10px;
    border-radius: 8px;
    background:    var(--evcc-surface-card, rgba(0, 0, 0, 0.20));
    border:        1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.12));
    color:         var(--evcc-text-primary, #f0f2f5);
    font-size:     0.9rem;
  }

  .evcc-setup-rename-input:focus {
    outline:      none;
    border-color: var(--evcc-accent, #3b9eff);
  }

  /* =========================================================
     ADD ANOTHER VACUUM
     ========================================================= */

  .evcc-setup-add-other {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    padding:        14px 16px;
    border-radius:  10px;
    background:     var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.10));
  }

  .evcc-setup-add-other-title {
    font-size:   0.95rem;
    font-weight: 700;
    color:       var(--evcc-text-primary, #f0f2f5);
  }

  .evcc-setup-add-other-list {
    display:        flex;
    flex-direction: column;
    gap:            8px;
  }

  .evcc-setup-add-other-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             12px;
    padding:         8px 10px;
    border-radius:   8px;
    background:      var(--evcc-surface-default, rgba(255, 255, 255, 0.04));
    border:          1px solid var(--evcc-border-subtle, rgba(255, 255, 255, 0.06));
  }

  .evcc-setup-add-other-info {
    display:        flex;
    flex-direction: column;
    gap:            2px;
    min-width:      0;
  }

  .evcc-setup-add-other-name {
    font-size:   0.88rem;
    font-weight: 600;
    color:       var(--evcc-text-primary, #f0f2f5);
  }
`;var Ji=`
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
    color: var(--evcc-text-secondary);
  }

  .evcc-mrev-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 600;
  }

  /* Redundant non-color cue: a per-state shape mark (src/renderers/
     badge-marks.js) so badges read without relying on hue \u2014 covers
     CVD + monochromacy, and disambiguates likely from warn (shared color). */
  .evcc-mrev-badge-mark {
    width: 0.95em;
    height: 0.95em;
    flex: none;
  }

  .evcc-mrev-badge--ok {
    background: color-mix(in srgb, var(--evcc-sem-success) 15%, transparent);
    color: var(--evcc-sem-success);
  }

  .evcc-mrev-badge--likely {
    background: color-mix(in srgb, var(--evcc-sem-warning) 12%, transparent);
    color: var(--evcc-sem-warning);
    font-style: italic;
  }

  .evcc-mrev-badge--warn {
    background: color-mix(in srgb, var(--evcc-sem-warning) 15%, transparent);
    color: var(--evcc-sem-warning);
  }

  .evcc-mrev-badge--outlier {
    background: color-mix(in srgb, var(--evcc-sem-error) 15%, transparent);
    color: var(--evcc-sem-error);
  }

  .evcc-mrev-badge--baseline {
    background: color-mix(in srgb, var(--evcc-sem-info) 15%, transparent);
    color: var(--evcc-sem-info);
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
    border-color: color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    background: color-mix(in srgb, var(--evcc-sem-error) 5%, transparent);
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
`;var Ki=`

  /* ===========================================================
     SHELL LAYOUT \u2014 mobile branch
     -----------------------------------------------------------
     Desktop shell flow:   header(nav) > view-stage > [empty] > [empty]
     Mobile shell flow:    header(no nav) > view-stage > bottom-nav > overlay

     The shell is already display:flex / flex-direction:column with
     height:100% (see shell.js). We just need:
       - Header: shrink to content (already correct)
       - View stage: flex:1, scrolls internally (already correct)
       - Bottom nav: shrink to content, sits at the bottom of the
         flex column naturally \u2014 no sticky/fixed required
       - Overlay: absolute, covers the whole shell when visible

     Earlier drafts used position:sticky on the bottom nav with a
     padding-bottom hack on the shell. That fights HA card height
     constraints in panel mode and leaves the nav floating mid-page
     when content is short. The flex-in-flow approach below is
     stable across all panel sizes.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] {
    position: relative;
    /* shell.js already sets height:100% and flex column on .evcc-shell;
       no overrides needed beyond making sure the host actually has
       full height. ha-card and the panel host take care of this in
       panel mode; for grid-card mode we still get a sensible result. */
  }

  /* On mobile, the regular desktop .evcc-nav inside the header is
     suppressed by replacing the header HTML \u2014 but the .evcc-nav
     fallback rule below makes sure no stale top nav ever leaks
     visually. */
  .evcc-shell[data-viewport="mobile"] .evcc-nav {
    display: none;
  }

  /* ===========================================================
     MOBILE HEADER
     ----------------------------------------------------------- */

  .evcc-mobile-header {
    display:     flex;
    flex-direction: column;
    gap:         2px;
    padding:     10px 14px;
    border-bottom: 1px solid var(--evcc-border-subtle);
    background:  var(--evcc-surface-panel);
    position:    sticky;
    top:         0;
    z-index:     9;
  }

  .evcc-mobile-vacuum-name {
    font-size:   1.05rem;
    font-weight: 600;
    color:       var(--evcc-text-primary);
    line-height: 1.2;
    overflow:    hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .evcc-mobile-vacuum-status {
    display:     flex;
    align-items: center;
    gap:         6px;
    font-size:   0.78rem;
    color:       var(--evcc-text-secondary);
  }

  .evcc-mobile-vacuum-status-label {
    text-transform: capitalize;
  }

  .evcc-mobile-battery {
    margin-left: auto;
    font-weight: 500;
    color:       var(--evcc-text-primary);
    font-variant-numeric: tabular-nums;
  }

  /* ===========================================================
     BOTTOM NAV
     -----------------------------------------------------------
     The shell is a flex column; this root is the last flex item
     and shrinks to its content height. View stage (flex:1) above
     consumes remaining space. No sticky/fixed positioning needed.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] [data-evcc-bottom-nav-root] {
    flex:         0 0 auto;        /* don't grow, don't shrink, size to content */
    z-index:      9;
    background:   var(--evcc-surface-panel);
    border-top:   1px solid var(--evcc-border-subtle);
    /* iOS notch / Android gesture bar inset. Padding is applied to
       the inner .evcc-mobile-nav so the border-top sits flush. */
  }

  /* On desktop the slot stays present but empty. flex:0 keeps it
     from claiming space. */
  .evcc-shell[data-viewport="desktop"] [data-evcc-bottom-nav-root] {
    display: none;
  }

  .evcc-mobile-nav {
    display:     flex;
    align-items: stretch;
    justify-content: space-around;
    padding:     4px 0;
    padding-bottom: max(4px, env(safe-area-inset-bottom));
  }

  .evcc-mobile-nav-tab {
    flex:        1 1 0;
    display:     flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap:         3px;
    padding:     6px 4px;
    min-height:  56px;                /* touch target */
    background:  transparent;
    border:      none;
    color:       var(--evcc-text-secondary);
    font-size:   0.7rem;
    font-weight: 500;
    cursor:      pointer;
    transition:  color 150ms ease;
  }

  .evcc-mobile-nav-tab:active {
    background:  var(--evcc-surface-raised);
  }

  .evcc-mobile-nav-tab.active {
    color:       var(--evcc-accent);
  }

  .evcc-mobile-nav-icon {
    width:       24px;
    height:      24px;
    display:     inline-flex;
    align-items: center;
    justify-content: center;
  }

  .evcc-mobile-nav-icon svg {
    width:       100%;
    height:      100%;
  }

  .evcc-mobile-nav-label {
    line-height: 1;
  }

  /* ===========================================================
     OVERFLOW SHEET ("More")
     -----------------------------------------------------------
     Bottom sheet that slides up over the bottom nav when the
     user taps the More tab. Backdrop is a full-card overlay
     that dismisses on tap.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] [data-evcc-mobile-overlay-root] {
    /* Container for sheet + backdrop. Absolute within the
       position:relative shell so backdrop dims the whole card.
       Empty when _mobileMoreOpen is false (renderer returns "");
       pointer-events:none on the container so an empty overlay
       never blocks the card. */
    position: absolute;
    inset:    0;
    pointer-events: none;
    z-index:  10;
  }

  /* Hidden on desktop. */
  .evcc-shell[data-viewport="desktop"] [data-evcc-mobile-overlay-root] {
    display: none;
  }

  .evcc-mobile-more-backdrop {
    position:     absolute;
    inset:        0;
    background:   rgba(0, 0, 0, 0.45);
    pointer-events: auto;
    animation:    evcc-mobile-fade-in 150ms ease-out both;
  }

  .evcc-mobile-more-sheet {
    position:     absolute;
    left:         0;
    right:        0;
    /* Sit above the bottom nav. The nav's height is dynamic
       (label + icon + padding + safe-area), so we use bottom:100%
       on a virtual reference. Concretely: the overlay container
       is the full shell, so we anchor to the same bottom as the
       shell \u2014 i.e. flush with the bottom nav above it. */
    bottom:       0;
    margin-bottom: 56px;      /* approx nav height; tighter than 64 */
    background:   var(--evcc-surface-panel);
    border-top:   1px solid var(--evcc-border-subtle);
    border-top-left-radius:  14px;
    border-top-right-radius: 14px;
    padding:      8px 0 max(8px, env(safe-area-inset-bottom));
    box-shadow:   0 -4px 24px rgba(0, 0, 0, 0.35);
    pointer-events: auto;
    animation:    evcc-mobile-slide-up 180ms ease-out both;
  }

  .evcc-mobile-more-handle {
    width:        38px;
    height:       4px;
    background:   var(--evcc-border-subtle);
    border-radius: 2px;
    margin:       4px auto 12px;
  }

  .evcc-mobile-more-item {
    display:      block;
    width:        100%;
    padding:      14px 20px;
    background:   transparent;
    border:       none;
    color:        var(--evcc-text-primary);
    font-size:    0.95rem;
    text-align:   left;
    cursor:       pointer;
    transition:   background-color 120ms ease;
  }

  .evcc-mobile-more-item:active {
    background:   var(--evcc-surface-raised);
  }

  .evcc-mobile-more-item.active {
    color:        var(--evcc-accent);
    font-weight:  600;
    background:   color-mix(in srgb, var(--evcc-accent) 10%, transparent);
  }

  @keyframes evcc-mobile-fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  @keyframes evcc-mobile-slide-up {
    from { transform: translateY(100%); }
    to   { transform: translateY(0); }
  }

  /* ===========================================================
     VIEW STAGE PADDING
     -----------------------------------------------------------
     Desktop has 20-24px of viewport padding via .evcc-view-stage.
     On mobile that eats too much horizontal real estate; tighten.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-view-stage {
    padding: 12px 10px;
  }

  /* ===========================================================
     ROOMS VIEW \u2014 mobile layout
     -----------------------------------------------------------
     Desktop is a side-by-side workspace: rooms grid on the left,
     Run Profiles aside on the right. On mobile both columns
     have to stack into a single scroll lane.

     Action bar: chips wrap; primary action chip claims full
     width so the Start button is the visually dominant target.

     Room card: order controls + gear shrink, name and chips
     remain readable; touch targets stay >=44px.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-workspace {
    /* Was a grid/flex split. Stack vertical. */
    display:        flex;
    flex-direction: column;
    gap:            14px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-main {
    width: 100%;
  }

  /* Force single-column room grid even at sizes above 720px
     when the card is rendered in mobile shell (e.g. landscape
     phones in a constrained panel). The existing
     @media (max-width: 720px) rule in rooms styles covers
     portrait; this is the belt-and-suspenders. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  /* Action bar \u2014 top row stacks vertically, chip group wraps. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar {
    padding: 10px;
    gap:     8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-bar-top {
    flex-direction: column;
    align-items:    stretch;
    gap:            10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-queue-summary {
    font-size: 0.9rem;
  }

  /* Primary action gets full width; secondary chips wrap below. */
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar .evcc-chips {
    display:         flex;
    flex-wrap:       wrap;
    gap:             8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar
    .evcc-chip[data-action="primary-room-action"] {
    flex:        1 1 100%;
    min-height:  48px;
    font-size:   1rem;
    font-weight: 600;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-action-bar
    .evcc-chip:not([data-action="primary-room-action"]) {
    /* Secondary chips: roughly half-width each so two fit per row,
       respecting the wrap when more than two exist. */
    flex:       1 1 calc(50% - 4px);
    min-height: 40px;
  }

  /* Room card tightening for narrow viewport. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-card {
    padding: 10px 12px;
    /* Make sure tap-to-toggle target stays generous. */
    min-height: 88px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-room-row-1 {
    /* Order controls + settings gear inline at top. */
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-order-controls {
    gap: 4px;
  }

  /* Mobile reorder uses the Move button (opens the position picker
     modal). The drag handle is hidden because HTML5 native drag
     (draggable=true + dragstart) does not fire from touch events,
     so the handle would be dead weight on touch devices. Earlier
     version had this backwards \u2014 handle visible, Move hidden \u2014 which
     left mobile users with no working reorder path. */
  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-order-drag-handle {
    display: none;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card .evcc-room-name {
    font-size:   1rem;
    line-height: 1.2;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-room-setting-chips {
    gap:        4px;
    flex-wrap:  wrap;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-room-card
    .evcc-room-setting-chip {
    font-size: 0.72rem;
    padding:   2px 6px;
  }

  /* ===========================================================
     RUN PROFILES PANEL \u2014 mobile layout
     -----------------------------------------------------------
     Desktop renders it as a right-hand aside. On mobile, drop it
     below the room grid and lay the saved profiles out as a
     horizontal scroll strip so the user can swipe through and
     tap one without losing the room grid above.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-panel {
    width:        100%;
    margin-top:   4px;
    border-radius: 10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list {
    display:           flex;
    flex-direction:    row;
    flex-wrap:         nowrap;
    overflow-x:        auto;
    scroll-snap-type:  x mandatory;
    gap:               8px;
    padding-bottom:    4px;
    /* Hide horizontal scrollbar visually \u2014 feels native. */
    scrollbar-width:   none;
  }
  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list::-webkit-scrollbar {
    display: none;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-run-profiles-list > * {
    flex:            0 0 auto;
    scroll-snap-align: start;
    min-width:       42vw;     /* roughly 2.2 profiles visible per screen */
  }

  /* ===========================================================
     LEARNING SUMMARY + BANNERS
     -----------------------------------------------------------
     Compact on mobile; tighter padding, smaller font for the
     metadata rows. Banners stay full-width.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-learning-summary,
  .evcc-shell[data-viewport="mobile"] .evcc-learning-prejob-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-learning-live-banner,
  .evcc-shell[data-viewport="mobile"] .evcc-incomplete-run-banner {
    padding:       10px 12px;
    font-size:     0.86rem;
    border-radius: 8px;
  }

  /* ===========================================================
     VIEW TOGGLE (list / map)
     -----------------------------------------------------------
     Buttons are tiny icon buttons. Bump them to thumb-friendly
     size on mobile.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn {
    min-width:  44px;
    min-height: 44px;
    padding:    8px;
  }
  .evcc-shell[data-viewport="mobile"] .evcc-rooms-view-toggle-btn svg {
    width:  20px;
    height: 20px;
  }

  /* ===========================================================
     MAP CONFIG VIEW \u2014 mobile layout
     -----------------------------------------------------------
     Desktop:  header (back btn + title)
               body  = [ map | side-panel 220px ]   horizontal split
               panel (image variants section)

     Mobile:   header (compact)
               body  = stacked vertical
                       [ map (60vh-ish) ]
                       [ side-panel full-width below ]
               panel (image variants \u2014 tighter)

     The map gets a fixed-ish viewport-relative height so it
     stays visible while the user reaches the adjustment buttons
     below. The side-panel becomes a scrollable region below the
     map. Vertex/edge nudge buttons grow to 44px touch targets.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-header {
    padding: 8px 10px;
    gap:     8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-back {
    /* Touch target \u2014 bump to 44px effective height via padding. */
    padding:    8px 12px 8px 8px;
    font-size:  0.9rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-title {
    font-size:  0.95rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-body {
    /* Was horizontal split \u2014 stack vertical on mobile. */
    flex-direction: column;
    min-height:     0;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-body
    > .evcc-map-container--config {
    /* Map fills the available width and gets ~55% of vertical
       space so the side-panel below is reachable without
       scrolling the whole card. */
    width:        100%;
    min-height:   0;
    flex:         0 0 55vh;
    position:     relative;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-side-panel {
    /* Was a 220px right column. Full width below the map now;
       scrolls internally if section content overflows. */
    width:          100%;
    border-left:    none;
    border-top:     1px solid var(--evcc-border-subtle);
    flex:           1 1 auto;
    min-height:     0;
    max-height:     45vh;
    padding-bottom: 8px;
  }

  /* ===========================================================
     NUDGE BUTTONS \u2014 touch sizing
     -----------------------------------------------------------
     Desktop: 36x36 directional, 28x28 edge. Mobile bumps both to
     44px so thumb taps land reliably.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-pad {
    /* Center the pad horizontally on mobile \u2014 desktop floats it
       to flex-start which looks lost on a full-width column. */
    align-self: center;
    gap:        6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-row {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn {
    width:      44px;
    height:     44px;
    font-size:  1.1rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn--edge {
    width:      44px;
    height:     44px;
    font-size:  1.1rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-nudge-btn--reset {
    font-size:  1rem;
  }

  /* Edge-grid rows: align label / value / +/- buttons across the
     wider mobile width. */
  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-grid {
    gap: 6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-row {
    gap: 8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-label {
    width:     60px;
    font-size: 0.85rem;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-edge-val {
    min-width: 36px;
    font-size: 0.85rem;
  }

  /* Vertex chips \u2014 make them tappable. */
  .evcc-shell[data-viewport="mobile"] .evcc-map-vertex-chips {
    gap: 6px;
  }

  /* ===========================================================
     CONFIG SECTIONS (sections inside the side panel)
     -----------------------------------------------------------
     Tighten padding on mobile but keep enough vertical
     separation that successive sections look like distinct
     control groups.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-section {
    padding: 12px 12px;
    gap:     12px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-section--hint {
    /* The "click a segment" placeholder gets dramatically tighter. */
    padding:    24px 16px;
    text-align: center;
  }

  /* ===========================================================
     CONFIG BOTTOM PANEL (Image Variants section)
     -----------------------------------------------------------
     Desktop renders this as the final row of the config view.
     On mobile that's still fine, just tighter.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-panel {
    border-top: 1px solid var(--evcc-border-subtle);
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-analyze-row {
    flex-wrap: wrap;
    gap:       8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-config-btn {
    min-height: 44px;
    padding:    10px 14px;
    font-size:  0.92rem;
  }

  /* ===========================================================
     ZOOM TOOLBAR (used by both Rooms map view and Config map)
     -----------------------------------------------------------
     Desktop sizes are fine for mouse but mobile needs bigger
     buttons. Also reposition to a thumb-reachable area when on
     a narrow viewport \u2014 bottom-right of the map container,
     not too far from where the thumb naturally rests.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-toolbar {
    /* Same corner as desktop, but more clearance from the edge
       and bigger touch targets. */
    right:   12px;
    bottom:  12px;
    padding: 6px 8px;
    gap:     6px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-btn {
    width:     40px;
    height:    40px;
    font-size: 18px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-map-zoom-readout {
    min-width: 48px;
    font-size: 13px;
  }

  /* ===========================================================
     CARD-LIKE PANEL VIEWS (Maintenance, Base Station, Metrics,
     Learning Review, Mapping Review)
     -----------------------------------------------------------
     All of these share a common structural pattern: a vertical
     .evcc-{view}-view container with a grid of panels using
     repeat(auto-fit, minmax(180px, 1fr)). At <360px the grids
     naturally collapse to 1fr, so structural CSS already works.

     What needs adjustment on mobile:
       - Panel padding: 16px \u2192 12px (saves 8px horizontal real
         estate, which matters at 360px viewport)
       - Inter-panel gap: 12px \u2192 10px
       - Stat / value font sizes: tighter
       - Buttons within panels: bump to 44px touch targets
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-review-panel,
  .evcc-shell[data-viewport="mobile"] .evcc-mapping-review-panel {
    padding: 12px;
    gap:     10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-view,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-view,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-view,
  .evcc-shell[data-viewport="mobile"] .evcc-review-view,
  .evcc-shell[data-viewport="mobile"] .evcc-mapping-review-view {
    gap: 10px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-review-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-mapping-review-grid {
    gap: 10px;
  }

  /* Force single-column on inner grids that use minmax(180px, 1fr).
     At 360px-12px-12px=336px available, a single 336px column wins
     over two ~160px ones for readability. */
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-stats,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-activity-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-action-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-card-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-stats,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-card-grid,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-window-grid {
    /* Two columns \u2014 most stats fit fine pair-wise on mobile,
       saves vertical space. */
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-base-station-stat,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-activity-card,
  .evcc-shell[data-viewport="mobile"] .evcc-base-station-action-card,
  .evcc-shell[data-viewport="mobile"] .evcc-maintenance-card,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-stat,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-card {
    padding: 10px;
    gap:     4px;
  }

  /* ===========================================================
     TABLES \u2014 horizontal scroll on overflow
     -----------------------------------------------------------
     The Metrics view uses <table> elements that have many
     columns and overflow on phones. Wrap them in an
     overflow-x:auto container by styling the table's parent.
     For tables without a dedicated wrapper, also tighten
     padding so they wrap less aggressively.
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table {
    font-size: 0.78rem;
    /* If the table itself overflows the panel, the parent panel's
       overflow:hidden would clip. Let it scroll within the panel. */
    display:     block;
    overflow-x:  auto;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table thead,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table tbody,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table tr {
    /* Required when table itself is display:block. */
    display: table;
    width:   100%;
    table-layout: auto;
  }

  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table th,
  .evcc-shell[data-viewport="mobile"] .evcc-metrics-table td {
    padding: 5px 8px;
  }

  /* ===========================================================
     ROOM RULES + THEME + SETUP \u2014 generic touch-target pass
     -----------------------------------------------------------
     These views are less table-heavy but include lots of
     buttons / form controls that default to ~32px on desktop.
     Generic 44px bump for any button inside a content view
     stage on mobile, except inside the bottom-tab nav (which
     has its own sizing).
     =========================================================== */

  .evcc-shell[data-viewport="mobile"] .evcc-view-stage button:not(
    .evcc-mobile-nav-tab,
    .evcc-mobile-more-item,
    .evcc-chip,
    .evcc-map-nudge-btn,
    .evcc-map-zoom-btn,
    .evcc-rooms-view-toggle-btn,
    .evcc-room-card *,
    .evcc-order-controls *
  ) {
    min-height: 44px;
  }

  /* Form inputs in modals / sidebar drawers \u2014 touch-sized. */
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="text"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="number"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage input[type="search"],
  .evcc-shell[data-viewport="mobile"] .evcc-view-stage select {
    min-height: 44px;
    font-size:  1rem;     /* avoid iOS auto-zoom on focus */
  }

  /* ===========================================================
     MODALS / SHEETS
     -----------------------------------------------------------
     Mobile modal styling lives in src/styles/index.js inside
     MODAL_HOST_STYLES under a @media (max-width: 600px) block,
     not here. The modal host is mounted on document.body (so the
     shell can be cleanly destroyed without ripping open modals),
     which means shell-data-attribute selectors here can't reach
     it across the document tree boundary. The viewport media
     query inside MODAL_HOST_STYLES is the right hook.
     =========================================================== */
`;var Yi=`
  .evcc-btn {
    border: 1px solid var(--evcc-border-default);
    background: var(--evcc-surface-input);
    color: var(--evcc-text-primary);
    border-radius: var(--evcc-radius-inner, 8px);
    padding: 8px 14px;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .evcc-btn:hover { background: var(--evcc-surface-panel); }
  .evcc-btn[disabled] { opacity: 0.5; cursor: default; }
  .evcc-btn-primary {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    color: var(--evcc-accent);
    font-weight: 600;
  }
  .evcc-btn-warn {
    background: color-mix(in srgb, var(--evcc-sem-warning) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-sem-warning) 40%, transparent);
    color: var(--evcc-sem-warning);
  }
  .evcc-btn-ghost { background: transparent; }
`,Qi=`
  .evcc-review-subtabs { display: flex; gap: 8px; margin-bottom: 14px; }
  .evcc-review-subtab {
    border: 1px solid var(--evcc-border-default);
    background: transparent;
    color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-chip, 999px);
    padding: 6px 16px;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .evcc-review-subtab.is-active {
    background: color-mix(in srgb, var(--evcc-accent) 18%, transparent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
    color: var(--evcc-accent);
    font-weight: 600;
  }
  .evcc-external-empty { padding: 24px; text-align: center; color: var(--evcc-text-secondary); }
  .evcc-external-list { display: flex; flex-direction: column; gap: 10px; }
  .evcc-external-card {
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 14px 16px;
    background: var(--evcc-surface-raised);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-card, 12px);
  }
  .evcc-external-card-title { font-weight: 600; color: var(--evcc-text-primary); }
  .evcc-external-card-meta { font-size: 0.82rem; color: var(--evcc-text-secondary); margin-top: 2px; }
  .evcc-external-card-actions { display: flex; gap: 8px; flex-shrink: 0; }
  ${Yi}
`,Xi=`
  .evcc-external-wizard-modal { max-width: 560px; width: 92vw; }
  .evcc-external-error {
    background: color-mix(in srgb, var(--evcc-sem-error) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--evcc-sem-error) 40%, transparent);
    color: var(--evcc-sem-error);
    border-radius: var(--evcc-radius-inner, 8px); padding: 8px 12px; margin-bottom: 12px; font-size: 0.85rem;
  }
  .evcc-ext-count {
    display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
    margin-bottom: 12px; color: var(--evcc-text-primary);
  }
  .evcc-ext-count-label { font-weight: 600; }
  .evcc-ext-stepper { display: inline-flex; align-items: center; gap: 8px; }
  .evcc-ext-step {
    width: 30px; height: 30px; padding: 0; font-size: 1.05rem; line-height: 1;
    display: inline-flex; align-items: center; justify-content: center;
  }
  .evcc-ext-count-n { min-width: 1.4em; text-align: center; font-size: 1.05rem; }
  .evcc-ext-seglist { display: flex; flex-direction: column; gap: 6px; }
  .evcc-ext-seg {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 10px; border-radius: var(--evcc-radius-inner, 8px);
    background: var(--evcc-surface-input);
  }
  .evcc-ext-seg.is-v2 { flex-direction: column; align-items: stretch; gap: 8px; }
  .evcc-ext-seg-row { display: flex; align-items: center; gap: 12px; }
  .evcc-ext-seg-start { font-size: 0.8rem; color: var(--evcc-text-secondary); min-width: 110px; }
  .evcc-ext-seg-facts { font-size: 0.82rem; color: var(--evcc-text-secondary); }
  .evcc-ext-split {
    min-width: 110px; text-align: left;
    border: 1px solid var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 5px 9px; font-size: 0.78rem; cursor: pointer;
  }
  .evcc-ext-split.is-split {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
  }
  /* v2 action-first controls \u2014 the label says what the button DOES. */
  .evcc-ext-merge {
    align-self: flex-start; min-width: 110px; text-align: left;
    border: 1px solid var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 5px 9px; font-size: 0.78rem; cursor: pointer;
  }
  .evcc-ext-merge:hover:not([disabled]) {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 40%, transparent);
  }
  .evcc-ext-splits { display: flex; flex-wrap: wrap; gap: 6px; padding-left: 12px; }
  .evcc-ext-split-here {
    border: 1px dashed var(--evcc-border-default);
    background: transparent; color: var(--evcc-text-secondary);
    border-radius: var(--evcc-radius-inner, 8px); padding: 4px 8px; font-size: 0.74rem; cursor: pointer;
  }
  .evcc-ext-split-here:hover:not([disabled]) {
    color: var(--evcc-accent);
    border-color: color-mix(in srgb, var(--evcc-accent) 50%, transparent);
  }
  .evcc-ext-step[disabled], .evcc-ext-merge[disabled], .evcc-ext-split-here[disabled] {
    opacity: 0.5; cursor: default;
  }
  .evcc-ext-room {
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-card, 12px); padding: 12px 14px; margin-bottom: 12px;
  }
  .evcc-ext-room-head { font-weight: 600; margin-bottom: 8px; color: var(--evcc-text-primary); }
  .evcc-ext-edge .evcc-field-label { color: var(--evcc-accent); }
  .evcc-ext-hint { font-size: 0.72rem; color: var(--evcc-text-secondary); font-weight: 400; }
  .evcc-ext-detected { font-size: 0.78rem; color: var(--evcc-text-secondary); margin-top: 6px; }
  .evcc-ext-allrooms {
    background: var(--evcc-surface-input);
    color: var(--evcc-text-primary);
    border: 1px solid var(--evcc-border-default);
    border-radius: var(--evcc-radius-inner, 8px); padding: 6px 8px; font-size: 0.82rem;
  }
  /* Native option popup ignores the var-based select bg on Windows Chrome and
     renders light text on a white system popup. Pin a solid dark bg + light text
     (concrete fallbacks) so the room list stays readable \u2014 mirrors
     .evcc-rooms-animal-select option. */
  .evcc-ext-allrooms option {
    background: var(--evcc-surface-panel, #1c2127);
    color:      var(--evcc-text-primary, #f0f2f5);
  }
  .evcc-ext-blocked { color: var(--evcc-sem-warning); font-size: 0.82rem; margin-bottom: 8px; }
  .evcc-modal-footer-row { display: flex; justify-content: space-between; gap: 8px; }
  ${Yi}
`;var Zi=[Ai,Ci,Ii,Oi,Li,Pi,Ni,Fi,At,Ct,Di,Hi,zi,Bi,ji,Vi,qi,Gi,Ui,Wi,Ji,Qi,Ki].join(`
`);function Ot(i,e){if(!i||!e)return;let{tokens:t}=e,r=i;ue.forEach(a=>{(!Object.prototype.hasOwnProperty.call(t,a.key)||t[a.key]===null||t[a.key]===void 0||t[a.key]==="")&&r.style.removeProperty(a.key)}),Object.entries(t).forEach(([a,c])=>{c!=null&&c!==""&&r.style.setProperty(a,c)})}var ec=`
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

  /* =========================================================
     MODAL TOKEN DERIVATION  (canonical -> modal family)
     =========================================================
     The modal host is mounted on document.body (and, in the render
     harness, as a shadow sibling) \u2014 DETACHED from the card's :host
     cascade, so it does NOT inherit the canonical --evcc-* seeds from
     foundation.js. Historically every --evcc-modal-* token therefore
     fell back to a HARD-CODED dark literal, which meant a theme that
     set only canonical tokens (surfaces / text / accent) left the
     modal stuck on the default palette.

     This block derives the whole modal colour family from the
     canonical tokens \u2014 the same mapping _build_release_theme_colors()
     bakes into every preloaded theme (themes/preloaded.py) \u2014 so ANY
     theme, hand- or AI-authored, themes its modals for free.

     Layering contract (why this is safe):
       - A theme writes --evcc-modal-* INLINE on .evcc-modal-host
         (apply-theme.js -> applyDynamicTheme(card._modalHost)). An
         inline declaration outranks these stylesheet rules, so an
         explicit modal override still wins.
       - Otherwise we chain to the canonical token (a theme sets those
         on the same host), so canonical-only themes flow through.
       - The final literal is the floor for a themeless body host
         (real-card default / Follow-HA, where no canonical reaches
         document.body). Floors reproduce the historical themeless render,
         except a few sub-perceptual cases that instead follow the coherent
         preloaded mapping (warning / accent-border opacities) \u2014 these appear
         in no visual baseline and differ only when NO theme is applied.
         modal-bg deliberately keeps the raw surface-base (preloaded's inline
         8% black darken still applies for the preloaded themes themselves),
         to keep the themeless default visually stable. A light companion of
         this block lives in the @media (prefers-color-scheme: light) rule
         below and supplies light floors for a themeless light-OS host.
     Size / shadow tokens are intentionally omitted \u2014 they are literal
     spec values, not canonical-derived colours.
     ========================================================= */
  .evcc-modal-host {
    /* Shell */
    --evcc-modal-bg:             var(--evcc-surface-base, #1c2127);
    --evcc-modal-backdrop-bg:    var(--evcc-surface-overlay, rgba(0, 0, 0, 0.72));
    --evcc-modal-border:         var(--evcc-border-default, rgba(255, 255, 255, 0.18));
    --evcc-modal-border-default: var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    --evcc-modal-border-strong:  var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
    --evcc-modal-border-subtle:  var(--evcc-border-subtle, rgba(255, 255, 255, 0.08));

    /* Surfaces */
    --evcc-modal-surface-panel:   var(--evcc-surface-panel, #1c2127);
    --evcc-modal-surface-input:   var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    --evcc-modal-surface-section: var(--evcc-surface-raised, rgba(255, 255, 255, 0.04));
    --evcc-modal-input-bg:        var(--evcc-surface-input, rgba(255, 255, 255, 0.06));

    /* Header / footer fills \u2014 transparent by default, so the floor
       collapses to transparent when no canonical surface is present. */
    --evcc-modal-header-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 86%, transparent);
    --evcc-modal-footer-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 80%, transparent);

    /* Text */
    --evcc-modal-text-primary:   var(--evcc-text-primary, #f0f2f5);
    --evcc-modal-text-secondary: var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    --evcc-modal-text-muted:     var(--evcc-text-muted, rgba(240, 242, 245, 0.48));

    /* Accent */
    --evcc-modal-accent:        var(--evcc-accent, #3b82f6);
    --evcc-modal-accent-text:   var(--evcc-accent, #3b82f6);
    --evcc-modal-accent-bg:     color-mix(in srgb, var(--evcc-accent, #3b82f6) 22%, transparent);
    --evcc-modal-accent-border: color-mix(in srgb, var(--evcc-accent, #3b82f6) 42%, transparent);

    /* Chips */
    --evcc-modal-chip-bg:           var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    --evcc-modal-chip-border:       var(--evcc-border-default, rgba(255, 255, 255, 0.10));
    --evcc-modal-chip-text:         var(--evcc-text-secondary, rgba(240, 242, 245, 0.72));
    --evcc-modal-chip-hover-bg:     var(--evcc-surface-panel, #1c2127);
    --evcc-modal-chip-hover-border: var(--evcc-border-strong, rgba(255, 255, 255, 0.18));
    --evcc-modal-chip-hover-text:   var(--evcc-text-primary, #f0f2f5);
    --evcc-modal-chip-active-bg:     var(--evcc-modal-accent-bg);
    --evcc-modal-chip-active-border: var(--evcc-modal-accent-border);
    --evcc-modal-chip-active-text:   var(--evcc-modal-accent-text);

    /* Warning (room-editor carpet notice) */
    --evcc-modal-warning-bg:     color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 16%, transparent);
    --evcc-modal-warning-border: color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 34%, transparent);
    --evcc-modal-warning-text:   color-mix(in srgb, var(--evcc-sem-warning, #f59e0b) 82%, white 18%);
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

    /* Map labels \u2014 pill behind centroid room names. The alpha keeps text
       legible over any backdrop (dark CV map or custom photo); dial it per map. */
    --evcc-map-label-bg:
      var(--evcc-map-label-bg, rgba(15, 18, 22, 0.60));

    --evcc-map-label-text:
      var(--evcc-map-label-text, #ffffff);

    --evcc-map-label-text-selected:
      var(--evcc-map-label-text-selected, #ffffff);

    --evcc-map-label-order-text:
      var(--evcc-map-label-order-text, #ffffff);

    --evcc-map-tooltip-bg:
      var(--evcc-map-tooltip-bg, rgba(15, 18, 22, 0.88));

    --evcc-map-tooltip-border:
      var(--evcc-map-tooltip-border, rgba(255, 255, 255, 0.12));

    --evcc-map-tooltip-text:
      var(--evcc-map-tooltip-text, #f0f2f5);

    --evcc-map-tooltip-hint:
      var(--evcc-map-tooltip-hint, rgba(240, 242, 245, 0.55));

    --evcc-map-compose-selected-stroke:
      var(--evcc-map-compose-selected-stroke, #ffffff);

    --evcc-map-compose-cut-fill:
      var(--evcc-map-compose-cut-fill, rgba(255, 92, 92, 0.12));

    --evcc-map-compose-cut-selected-fill:
      var(--evcc-map-compose-cut-selected-fill, rgba(255, 92, 92, 0.20));

    --evcc-map-vertex-selected-glow:
      var(--evcc-map-vertex-selected-glow, rgba(255, 221, 0, 0.9));

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
  .evcc-editor-field-groups,
  .evcc-modal-body {
    flex:           1;
    min-height:     0;       /* Required for flex children to actually
                                shrink-and-scroll instead of growing
                                past their parent's max-height. */
    overflow-y:     auto;
    padding:        var(--evcc-modal-padding, 20px);
    display:        flex;
    flex-direction: column;
    gap:            var(--evcc-modal-section-gap, 28px);
  }

  /* Export / Import theme-JSON modal \u2014 wider, with a monospace text area.
     Canonical tokens resolve to the modal-derived family inside .evcc-modal. */
  .evcc-modal--theme-json { max-width: 600px; }

  .evcc-modal--theme-json .evcc-modal-body { gap: 10px; }

  .evcc-theme-json-hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--evcc-text-secondary, rgba(255, 255, 255, 0.7));
  }

  .evcc-theme-json-area {
    width: 100%;
    min-height: 240px;
    max-height: 48vh;
    resize: vertical;
    font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--evcc-text-primary, #f0f2f5);
    background: var(--evcc-surface-input, rgba(255, 255, 255, 0.06));
    border: 1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.16));
    border-radius: var(--evcc-radius-inner, 10px);
    padding: 10px 12px;
    white-space: pre;
    overflow: auto;
  }

  .evcc-theme-json-area:focus {
    outline: none;
    border-color: var(--evcc-accent, #3b82f6);
  }

  .evcc-theme-json-error {
    margin: 0;
    font-size: 0.82rem;
    color: var(--evcc-sem-error, #e05252);
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

  ${Mt}

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

  ${It}
  ${At}
  ${Ct}
  ${Xi}

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
    /* Light companion to the .evcc-modal-host derivation block above. The body
       modal host is detached from :host, so when themeless the canonical-derived
       defaults resolve to their DARK floors \u2014 which would shadow this media
       query's light fallbacks and leave a light-OS Follow-HA user with a dark
       modal. Re-derive the surface/text/border family here with LIGHT floors.
       A theme still wins (it sets --evcc-modal-* / canonical inline on the host,
       and the canonical chain is honoured in either scheme); the light literals
       only apply to a genuinely themeless light-OS host. Accent / warning /
       chip-active tokens are scheme-neutral and inherit the block above. */
    .evcc-modal-host {
      --evcc-modal-bg:             var(--evcc-surface-base, #ffffff);
      --evcc-modal-backdrop-bg:    var(--evcc-surface-overlay, rgba(15, 23, 42, 0.28));
      --evcc-modal-border:         var(--evcc-border-default, rgba(15, 23, 42, 0.12));
      --evcc-modal-border-default: var(--evcc-border-default, rgba(15, 23, 42, 0.10));
      --evcc-modal-border-strong:  var(--evcc-border-strong, rgba(15, 23, 42, 0.16));
      --evcc-modal-border-subtle:  var(--evcc-border-subtle, rgba(15, 23, 42, 0.06));

      --evcc-modal-surface-panel:   var(--evcc-surface-panel, #ffffff);
      --evcc-modal-surface-input:   var(--evcc-surface-input, rgba(15, 23, 42, 0.05));
      --evcc-modal-surface-section: var(--evcc-surface-raised, rgba(15, 23, 42, 0.03));
      --evcc-modal-input-bg:        var(--evcc-surface-input, rgba(15, 23, 42, 0.05));

      --evcc-modal-header-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 86%, transparent);
      --evcc-modal-footer-bg: color-mix(in srgb, var(--evcc-surface-panel, transparent) 80%, transparent);

      --evcc-modal-text-primary:   var(--evcc-text-primary, #0f172a);
      --evcc-modal-text-secondary: var(--evcc-text-secondary, rgba(15, 23, 42, 0.74));
      --evcc-modal-text-muted:     var(--evcc-text-muted, rgba(15, 23, 42, 0.50));

      --evcc-modal-chip-bg:           var(--evcc-surface-input, rgba(15, 23, 42, 0.05));
      --evcc-modal-chip-border:       var(--evcc-border-default, rgba(15, 23, 42, 0.10));
      --evcc-modal-chip-text:         var(--evcc-text-secondary, rgba(15, 23, 42, 0.74));
      --evcc-modal-chip-hover-bg:     var(--evcc-surface-panel, #ffffff);
      --evcc-modal-chip-hover-border: var(--evcc-border-strong, rgba(15, 23, 42, 0.16));
      --evcc-modal-chip-hover-text:   var(--evcc-text-primary, #0f172a);
    }

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

  /* =========================================================
     MOBILE \u2014 bottom-sheet layout
     =========================================================
     At phone widths the centered desktop modal wastes vertical
     space and crops content that exceeds 85vh without an obvious
     scroll affordance. Switch to a bottom-sheet pattern:
     full-width, pinned to bottom, drag handle, sticky header +
     footer so the user always sees where they are.

     The @media query lives inside MODAL_HOST_STYLES rather than
     in mobile.js because the modal host is mounted on document.body
     (not inside the card shadow root), so the shell-data-attribute
     selectors in mobile.js never reach it.
     ========================================================= */
  @media (max-width: 600px) {
    .evcc-modal-backdrop {
      /* Pin to bottom \u2014 modal rises from the edge of the screen.
         Zero padding so the sheet can use the full width and
         extend to viewport bottom for a true bottom-sheet feel. */
      align-items: flex-end;
      padding: 0;
    }

    .evcc-modal {
      max-width:    100%;
      width:        100%;
      max-height:   92vh;
      border-radius: 16px 16px 0 0;
      border-bottom-left-radius:  0;
      border-bottom-right-radius: 0;
      border-bottom-width: 0;
      box-shadow:   0 -8px 32px rgba(0, 0, 0, 0.55);
      /* Pad bottom for iOS home-indicator safe area. */
      padding-bottom: env(safe-area-inset-bottom, 0px);
    }

    /* No drag handle. An earlier version drew a pill at the top
       of the sheet to signal "this is dismissible" but swipe-to-
       dismiss was never wired, so the affordance promised a
       gesture that didn't exist. Removed entirely; the X button
       in the header is the canonical close path. Add back when /
       if a real swipe gesture handler ships. */

    /* Sticky header \u2014 title + close button stay visible while
       the body scrolls. Background matches modal so scrolled
       content doesn't bleed through. */
    .evcc-modal-header {
      position:  sticky;
      top:       0;
      z-index:   2;
      background: var(--evcc-modal-bg, #1c2127);
    }

    /* Sticky footer \u2014 action buttons stay reachable without
       scrolling down. Top border separates from scrolled content. */
    .evcc-modal-footer {
      position:  sticky;
      bottom:    0;
      z-index:   2;
      background: var(--evcc-modal-bg, #1c2127);
      border-top:
        1px solid var(--evcc-modal-border-subtle,
        var(--evcc-border-default, rgba(255, 255, 255, 0.12)));
    }

    /* Body: a touch of extra bottom padding so the last row of
       content doesn't sit flush against the sticky footer when
       scrolled to the bottom. */
    .evcc-modal-body {
      padding-bottom: 20px;
    }
  }

  /* =========================================================
     REORDER MODAL \u2014 current order + preview chip rows
     =========================================================
     "Currently" / "After move" sections in the position selector
     modal show every item in the list as a small chip with its
     position number. Active item is filled with the accent color
     so the user can spot it instantly in both rows.

     Rules live here (not in styles/order.js) because the modal
     host is body-attached, outside the card shadow root.
     ========================================================= */

  .evcc-order-preview-row {
    display:        flex;
    flex-wrap:      wrap;
    gap:            6px;
  }

  .evcc-order-preview-chip {
    display:        inline-flex;
    align-items:    center;
    gap:            6px;
    padding:        4px 10px 4px 4px;
    border-radius:  999px;
    font-size:      0.8rem;
    line-height:    1.2;
    background:     var(--evcc-surface-subtle, rgba(255,255,255,0.04));
    border:         1px solid var(--evcc-border-subtle, rgba(255,255,255,0.10));
    color:          var(--evcc-text-secondary);
  }

  .evcc-order-preview-chip-pos {
    display:        inline-flex;
    align-items:    center;
    justify-content: center;
    min-width:      18px;
    height:         18px;
    padding:        0 5px;
    border-radius:  999px;
    font-size:      0.72rem;
    font-weight:    700;
    background:     var(--evcc-surface-subtle, rgba(255,255,255,0.08));
    color:          var(--evcc-text-muted);
  }

  .evcc-order-preview-chip--active {
    background:     color-mix(in srgb, var(--evcc-accent, #60a5fa) 18%, transparent);
    border-color:   color-mix(in srgb, var(--evcc-accent, #60a5fa) 60%, transparent);
    color:          var(--evcc-text-primary);
    font-weight:    600;
  }

  .evcc-order-preview-chip--active .evcc-order-preview-chip-pos {
    background:     var(--evcc-accent, #60a5fa);
    color:          var(--evcc-text-on-accent, #ffffff);
  }
`,tc=`
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

  .evcc-toast-stack {
    position:        fixed;
    left:            0;
    right:           0;
    bottom:          24px;
    display:         flex;
    flex-direction:  column-reverse;
    gap:             8px;
    align-items:     center;
    pointer-events:  none;
    z-index:         10000;
    font-family:     var(--evcc-font-family, var(--paper-font-body1_-_font-family, sans-serif));
    font-size:       14px;
  }

  .evcc-toast {
    pointer-events: auto;
    display:        flex;
    align-items:    center;
    gap:            10px;
    padding:        10px 14px;
    border-radius:  10px;
    font-size:      0.9rem;
    background:     var(--evcc-surface-raised, rgba(28, 28, 30, 0.96));
    color:          var(--evcc-text-primary, #f0f2f5);
    box-shadow:     0 6px 18px rgba(0, 0, 0, 0.4);
    border:         1px solid var(--evcc-border-default, rgba(255, 255, 255, 0.1));
    min-width:      220px;
    max-width:      90vw;
    animation:      evcc-toast-host-in 160ms ease-out;
  }

  .evcc-toast--success { border-left: 3px solid var(--evcc-sem-success, #22c55e); }
  .evcc-toast--error   { border-left: 3px solid var(--evcc-sem-error,   #ef4444); }
  .evcc-toast--info    { border-left: 3px solid var(--evcc-accent,      #60a5fa); }

  .evcc-toast-message {
    flex: 1;
    line-height: 1.3;
  }

  .evcc-toast-dismiss {
    color:        var(--evcc-text-muted, rgba(255, 255, 255, 0.55));
    font-size:    0.95rem;
    padding:      0 6px;
    line-height:  1;
  }

  .evcc-toast-dismiss:hover {
    color: var(--evcc-text-primary, #f0f2f5);
  }

  @keyframes evcc-toast-host-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;function Q(i){let e=i._state;if(!e||typeof e.resolvedTheme!="function")return;let t=e.resolvedTheme();Ot(i,t),i._modalHost&&document.body.contains(i._modalHost)&&Ot(i._modalHost,t)}function Qn(i){if(!i)return null;let e=i.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);if(!e)return null;let[,t,r,a]=e;return"#"+[t,r,a].map(c=>parseInt(c,10).toString(16).padStart(2,"0")).join("")}var rc=new Set(["--evcc-accent","--evcc-surface-base","--evcc-text-primary","--evcc-radius-card"]),Xn=300,ac=6;function ic(i){i._applyScopedThemeImport=async function(e,t){let{known:r,unknown:a}=Ga(e);if(!r.length)return alert(`${t} has no floor types this version recognises`+(a.length?` (unsupported: ${a.join(", ")}).`:".")),!1;if(!confirm(`Replace these floor types on the active theme:
  ${r.join(", ")}`+(a.length?`

Skipped \u2014 unsupported in this version:
  ${a.join(", ")}`:"")+`

This overwrites those types. Continue?`))return!1;let{envelope:n,corrected:s}=Ja(e,ye);return await this.card._actions.importTheme({...n,scope:r},this.card._config.vacuum_entity_id),await this._refreshThemeFromBackend(),alert(`Replaced ${r.join(", ")} from ${t}.`+(s?` ${s} value(s) clamped to range.`:"")+(a.length?` Skipped: ${a.join(", ")}.`:"")),!0},i._bindThemeEditor=function(){this._bindThemeTabs(),this._bindThemePresets(),this._bindThemeMode(),this._bindPresetFilters(),this._bindPresetTagEditor(),this._bindThemeGroupFilters(),this._bindThemeGroupToggles(),this._bindThemeGlobalSearch(),this._bindThemeGroupSearch(),this._bindThemeTokenEdits(),this._bindThemeAlphaEdits(),this._bindThemeColorMixEdits(),this._bindThemeTokenResets(),this._bindThemeGroupResets(),this._bindThemeColorPickerFromAlphaInput(),this._bindThemeActions()},i._bindThemeTabs=function(){this.card._onAll("[data-theme-tab]","click",e=>{let t=e.currentTarget.dataset.themeTab;this.card._state.setThemeSubTab(t),this.card._scheduleRender()})},i._bindThemePresets=function(){this.card._onAll("[data-theme-preset]","click",async e=>{let t=e.currentTarget.dataset.themePreset;if(!t)return;if(this.card._state.isDeviceThemeMode()){this.card._state.setDeviceThemeId(t),Q(this.card),this.card._scheduleRender();return}let r=await this.card._actions.setActiveTheme(this.card._config.vacuum_entity_id,t);if(r?.ok===!1){alert(r.reason||"Unable to select theme.");return}let a=r?.active_theme_id??r?.theme_id??t;this.card._state.applyThemeActivation(a,{clearDraft:r?.draft_dirty===!1}),Q(this.card),this.card._scheduleRender(),await this._refreshThemeFromBackend({fallbackActiveThemeId:a,fallbackDraftDirty:!1})})},i._bindThemeMode=function(){this.card._onAll("[data-theme-mode]","click",e=>{this.card._state.setThemeMode(e.currentTarget.dataset.themeMode),Q(this.card),this.card._scheduleRender()}),this.card._onAll("[data-action='theme-use-everywhere']","click",async()=>{let e=this.card._state.getDeviceThemeId()||this.card._state.effectiveActiveThemeId();if(!e)return;let t=await this.card._actions.setActiveTheme(this.card._config.vacuum_entity_id,e);if(!t?.ok){alert(t?.reason||"Unable to apply for everyone.");return}let r=t?.active_theme_id??t?.theme_id??e;this.card._state.applyThemeActivation(r,{clearDraft:t?.draft_dirty===!1}),this.card._state.clearDeviceOverride(),Q(this.card),this.card._scheduleRender(),await this._refreshThemeFromBackend({fallbackActiveThemeId:r,fallbackDraftDirty:!1})}),this.card._onAll("[data-action='theme-clear-device']","click",()=>{this.card._state.clearDeviceOverride(),Q(this.card),this.card._scheduleRender()})},i._bindPresetFilters=function(){this.card._onAll("[data-preset-facet]","click",e=>{let t=e.currentTarget.dataset.presetFacet,r=e.currentTarget.dataset.presetFacetValue;!t||!r||(this.card._state.togglePresetFacet(t,r),this.card._scheduleRender())}),this.card._on(this.card.$("[data-preset-search]"),"input",e=>{this.card._state.setPresetSearchQuery(e.target.value),this.card._scheduleRender()}),this.card._onAll("[data-preset-clear]","click",()=>{this.card._state.clearPresetFilters(),this.card._scheduleRender()}),this.card._onAll("[data-preset-filters-toggle]","click",()=>{this.card._state.togglePresetFilters(),this.card._scheduleRender()})},i._bindPresetTagEditor=function(){this.card._onAll("[data-preset-tag-edit]","click",e=>{e.stopPropagation();let t=e.currentTarget.dataset.presetTagEdit,r=this.card._state.getPresetTagEditId();this.card._state.setPresetTagEditId(r===t?null:t),this.card._scheduleRender()}),this.card._onAll("[data-preset-tag-editor]","click",e=>e.stopPropagation()),this.card._onAll("[data-preset-tag-done]","click",e=>{e.stopPropagation(),this.card._state.setPresetTagEditId(null),this.card._scheduleRender()}),this.card._onAll("[data-preset-tag-remove]","click",async e=>{e.stopPropagation();let t=e.currentTarget.dataset.presetTagRemove,r=e.currentTarget.dataset.tag,a=this.card._state.presetVibeTags(t).filter(c=>c!==r);await this._persistThemeTags(t,a)}),this.card._onAll("[data-preset-tag-add]","keydown",async e=>{if(e.key!=="Enter")return;e.stopPropagation(),e.preventDefault();let t=e.currentTarget.dataset.presetTagAdd,r=String(e.currentTarget.value||"").trim().toLowerCase();if(!r)return;let a=this.card._state.presetVibeTags(t);if(a.includes(r)){e.currentTarget.value="";return}await this._persistThemeTags(t,[...a,r])})},i._persistThemeTags=async function(e,t){let r=this.card._state.presetVibeTags(e);this.card._state.applyThemeTagsLocal(e,t),this.card._scheduleRender();let a=await this.card._actions.setThemeTags(e,t);a?.ok||(this.card._state.applyThemeTagsLocal(e,r),this.card._scheduleRender(),alert(a?.reason||"Unable to update tags."))},i._bindThemeJsonModalHost=function(e){e.querySelectorAll("[data-action='close-theme-json']").forEach(t=>{t.addEventListener("click",()=>{this.card._state.closeThemeJsonModal(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='copy-theme-json']").forEach(t=>{t.addEventListener("click",async()=>{let r=e.querySelector("[data-theme-json-area]");if(!r)return;r.focus(),r.select();let a=!1;try{navigator.clipboard&&navigator.clipboard.writeText&&(await navigator.clipboard.writeText(r.value),a=!0)}catch{a=!1}if(!a)try{a=document.execCommand("copy")}catch{a=!1}t.textContent=a?"Copied!":"Select + Ctrl+C",setTimeout(()=>{t.textContent="Copy"},1800)})}),e.querySelectorAll("[data-action='notify-theme-json']").forEach(t=>{t.addEventListener("click",async()=>{let r=e.querySelector("[data-theme-json-area]"),a=r?r.value:this.card._state.themeJsonModalText(),c=this.card._state._ensureThemeState(),n=this.card._state.effectiveActiveThemeId(),s=c.library?.[n]?.name||n||"theme";t.disabled=!0,t.textContent="Sending\u2026";let o=await this.card._actions.notifyThemeExport(n,s,a);t.textContent=o?"Sent to HA \u2713":"Failed \u2014 see logs",setTimeout(()=>{t.textContent="Send to HA",t.disabled=!1},1800)})}),e.querySelectorAll("[data-action='confirm-theme-import']").forEach(t=>{t.addEventListener("click",async()=>{let r=e.querySelector("[data-theme-json-area]"),a=e.querySelector("[data-theme-json-error]"),c=l=>{a&&(a.textContent=l,a.hidden=!1)},n=r?r.value.trim():"";if(!n){c("Paste a theme export first.");return}let s;try{s=JSON.parse(n)}catch{c("That isn't valid JSON \u2014 check the pasted text.");return}let o=await this.card._actions.importTheme(s);if(o?.ok===!1){c(`Import failed: ${o.reason||"unknown error"}.`);return}this.card._state.closeThemeJsonModal(),this.card._scheduleRender(),await this._refreshThemeFromBackend()})})},i._bindThemeGroupFilters=function(){this.card._onAll("[data-theme-group-filter]","click",e=>{let t=e.currentTarget.dataset.themeGroupFilter||"all";this.card._state.setThemeGroupFilter(t),ae.includes(t)&&this.card._state.setThemeFocusedGroup(t),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()})},i._bindThemeGroupToggles=function(){this.card._onAll("[data-theme-group-toggle]","click",e=>{let t=e.currentTarget.dataset.themeGroupToggle;t&&(this.card._state.setThemeFocusedGroup(t),this.card._state.toggleThemeGroup(t),this.card._scheduleRender())})},i._bindThemeGlobalSearch=function(){this.card._on(this.card.$("[data-theme-search]"),"input",e=>{this.card._state.setThemeSearchQuery(e.target.value),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-theme-modified-only]"),"change",e=>{this.card._state.setThemeModifiedOnly(e.target.checked),this._autoOpenMatchingThemeGroups(),this.card._scheduleRender()})},i._bindThemeGroupSearch=function(){this.card._onAll("[data-theme-group-search]","input",e=>{let t=e.currentTarget.dataset.themeGroupSearch;t&&(this.card._state.setThemeFocusedGroup(t),this.card._state.setThemeGroupSearchQuery(t,e.target.value),this.card._scheduleRender())})},i._bindThemeTokenEdits=function(){this.card._onAll("[data-theme-token]","input",async e=>{let t=e.currentTarget.dataset.themeToken,r=ye[t];if(!r)return;let a=e.currentTarget.type==="range",c=e.currentTarget.value;this.card._state.setThemeFocusedGroup(r.group),this._syncThemeRowInputs(e.currentTarget,t),this._isScalarThemeType(r.type)&&(c=this._formatScalarThemeValue(c,r,e.currentTarget));let n=this._buildDraftPayload(t,c,r);if(!Object.keys(n).length)return;!a&&this._isSettledThemeValue(c,r)&&await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,n),this.card._state.applyThemeDraftPatch(n),Q(this.card)}),this.card._onAll("[data-theme-color-input]","change",async e=>{let t=e.currentTarget.dataset.themeColorInput,r=ye[t];if(!r)return;let a=e.currentTarget.value||"";this.card._state.setThemeFocusedGroup(r.group),this._syncThemeRowInputs(e.currentTarget,t,a);let c=this._buildDraftPayload(t,a,r);Object.keys(c).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,c),this.card._state.applyThemeDraftPatch(c),Q(this.card),this.card._scheduleDeferredRender?.())}),this.card._onAll("[data-theme-token]","change",async e=>{if(e.currentTarget.type==="range"){let r=e.currentTarget.dataset.themeToken,a=ye[r];if(a){let c=e.currentTarget.value;this._isScalarThemeType(a.type)&&(c=this._formatScalarThemeValue(c,a,e.currentTarget));let n=this._buildDraftPayload(r,c,a);Object.keys(n).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,n),this.card._state.applyThemeDraftPatch(n),Q(this.card))}}this.card._scheduleDeferredRender?.()})},i._bindThemeAlphaEdits=function(){this.card._onAll("[data-theme-alpha]","input",e=>{let t=e.currentTarget.dataset.themeAlpha;if(!t)return;let r=ye[t];r?.group&&this.card._state.setThemeFocusedGroup(r.group);let a=this._clampThemeAlphaPercent(e.currentTarget.value);this._syncThemeAlphaControls(t,a,e.currentTarget),this.card._state.applyThemeDraftPatch({alpha:{[t]:a/100}}),Q(this.card)}),this.card._onAll("[data-theme-alpha]","change",async e=>{let t=e.currentTarget.dataset.themeAlpha;if(!t)return;let r=this._clampThemeAlphaPercent(e.currentTarget.value);await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,{alpha:{[t]:r/100}}),Q(this.card),this.card._scheduleDeferredRender?.()})},i._clampThemeAlphaPercent=function(e){let t=Number(e);return Number.isNaN(t)?100:Math.max(0,Math.min(100,Math.round(t)))},i._syncThemeAlphaControls=function(e,t,r=null){let a=r?r.closest(".evcc-token-row"):this.card.shadowRoot?.querySelector(`[data-theme-alpha="${e}"]`)?.closest(".evcc-token-row");if(!a)return;let c=a.querySelector(`[data-theme-alpha="${e}"]`),n=a.querySelector(`[data-theme-alpha-bubble="${e}"]`),s=a.querySelector(`[data-theme-alpha-indicator="${e}"]`),o=a.querySelector(".token-alpha-shell"),l=a.querySelector(".token-alpha-rail");if(c&&(c.value=String(t)),!c)return;let d=Number(c.min)||0,u=Number(c.max)||100,m=Number(c.value)||0,p=u===d?0:(m-d)/(u-d);if(s&&l){let v=l.clientWidth,f=p*v;s.style.left=`${f}px`}if(n&&o){let v=o.clientWidth,f=p*v;n.style.left=`${f}px`,n.textContent=`${m}%`}},i._syncThemeRowInputs=function(e,t,r=null){let a=e.closest(".evcc-token-row");if(!a)return;let c=r??e.value;a.querySelectorAll(`[data-theme-token="${t}"], [data-theme-color-input="${t}"]`).forEach(n=>{n!==e&&(n.value=c)}),this._syncThemeScalarControls(a,t,c)},i._syncThemeScalarControls=function(e,t,r){if(!e)return;let a=e.querySelector(`[data-theme-slider-bubble="${t}"]`);if(!a)return;let c=e.dataset.themeTokenUnit||"",n=e.querySelector(`input[type="range"][data-theme-token="${t}"]`);n&&(n.value=r),a.textContent=`${r}${c}`},i._isSettledThemeValue=function(e,t){if(!t||t.type!=="color")return!0;let r=String(e||"").trim();return!!(!r||/^#[0-9a-fA-F]{6}$/.test(r)||/^#[0-9a-fA-F]{8}$/.test(r)||/^color-mix\(.*%.*\)$/is.test(r)||/^var\(--[\w-]+\)$/.test(r))},i._isScalarThemeType=function(e){return e==="size"||e==="number"||e==="duration"},i._extractThemeScalarUnit=function(e,t=""){let r=String(t||"").trim();if(e?.type==="duration"){let a=r.match(/^-?\d*\.?\d+\s*(ms|s)$/i);return a?a[1].toLowerCase():"ms"}if(e?.type==="size"){let a=r.match(/^-?\d*\.?\d+\s*(px|rem|em|%|vh|vw|vmin|vmax|ch|ex)$/i);return a?a[1].toLowerCase():"px"}return""},i._formatScalarThemeValue=function(e,t,r=null){let a=parseFloat(String(e||"").trim());if(Number.isNaN(a))return"";if(t?.type==="number")return`${a}`;let c=r?.closest(".evcc-token-row")||null,n=c?.dataset.themeTokenUnit?`${a}${c.dataset.themeTokenUnit}`:e,s=this._extractThemeScalarUnit(t,n);return`${a}${s}`},i._buildDraftPayload=function(e,t,r=null){let a=r||ye[e];return a?a.type==="color"?{tokens:{[e]:t},colors:{[e]:t}}:a.type==="alpha"?{alpha:{[e]:t}}:{tokens:{[e]:t}}:{}},i._bindThemeColorMixEdits=function(){this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']","input",e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row");if(!r)return;let a=Math.max(0,Math.min(100,Math.round(Number(e.currentTarget.value)))),c=r.querySelector(`[data-colormix-ratio-label="${t}"]`);c&&(c.textContent=`${a}%`);let n=this._readColorMixExpr(r,t,{ratio:a});n&&(this.card._state.applyThemeDraftPatch({tokens:{[t]:n},colors:{[t]:n}}),Q(this.card),this._syncColorMixPreview(r,n))}),this.card._onAll("[data-theme-colormix][data-colormix-part='ratio']","change",async e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=Math.max(0,Math.min(100,Math.round(Number(e.currentTarget.value)))),c=this._readColorMixExpr(r,t,{ratio:a});if(!c)return;let n={tokens:{[t]:c},colors:{[t]:c}};await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,n),this.card._state.applyThemeDraftPatch(n),Q(this.card),this.card._scheduleDeferredRender?.()}),this.card._onAll("[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']","change",async e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=this._readColorMixExpr(r,t);if(!a)return;let c={tokens:{[t]:a},colors:{[t]:a}};await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,c),this.card._state.applyThemeDraftPatch(c),Q(this.card),this._syncColorMixPreview(r,a),this.card._scheduleDeferredRender?.()}),this.card._onAll("[data-theme-colormix][data-colormix-part='color1'], [data-theme-colormix][data-colormix-part='color2']","input",e=>{let t=e.currentTarget.dataset.themeColormix;if(!t)return;let r=e.currentTarget.closest(".evcc-token-row"),a=this._readColorMixExpr(r,t);a&&this._syncColorMixPreview(r,a)})},i._readColorMixExpr=function(e,t,r={}){if(!e)return null;let a=e.querySelector('[data-colormix-part="color1"]'),c=e.querySelector('[data-colormix-part="color2"]'),n=e.querySelector('[data-colormix-part="ratio"]');if(!a||!c||!n)return null;let s=(a.value||"").trim(),o=(c.value||"").trim(),l="ratio"in r?r.ratio:Math.max(0,Math.min(100,Math.round(Number(n.value))));return!s||!o?null:`color-mix(in srgb, ${s} ${l}%, ${o} ${100-l}%)`},i._syncColorMixPreview=function(e,t){if(!e||!t)return;let r=e.querySelector(".token-colormix-preview");r&&(r.style.background=t)},i._bindThemeTokenResets=function(){this.card._onAll("[data-theme-reset]","click",async e=>{let t=e.currentTarget.dataset.themeReset,r=ye[t];if(!r)return;this.card._state.setThemeFocusedGroup(r.group);let a=this._buildDraftResetPayload(t,r);Object.keys(a).length&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,a),this.card._state.applyThemeDraftPatch(a),await this._refreshThemeFromBackend())})},i._buildDraftResetPayload=function(e,t){return t.type==="color"?{tokens:{[e]:null},colors:{[e]:null},alpha:{[e]:null}}:t.type==="alpha"?{alpha:{[e]:null}}:{tokens:{[e]:null}}},i._bindThemeGroupResets=function(){this.card._onAll("[data-theme-group-reset]","click",async e=>{e.stopPropagation();let t=e.currentTarget.dataset.themeGroupReset;if(!t)return;this.card._state.setThemeFocusedGroup(t);let r=this._buildThemeGroupResetPayload(t);r&&(await this.card._actions.updateWorkingDraft(this.card._config.vacuum_entity_id,r),await this._refreshThemeFromBackend())})},i._buildThemeGroupResetPayload=function(e){let t=this.card._state.filteredThemeTokensForGroup(e,ue,{excludeKeys:rc}),{sources:r}=this.card._state.resolvedTheme(),a={},c={},n={},s=!1;if(t.forEach(l=>{(r[l.key]||"ha")==="draft"&&(l.type==="color"?(a[l.key]=null,c[l.key]=null,n[l.key]=null,s=!0):l.type==="alpha"?(n[l.key]=null,s=!0):(a[l.key]=null,s=!0))}),!s)return null;let o={};return Object.keys(a).length&&(o.tokens=a),Object.keys(c).length&&(o.colors=c),Object.keys(n).length&&(o.alpha=n),o},i._bindThemeColorPickerFromAlphaInput=function(){this._alphaTapMap||(this._alphaTapMap=new Map);let e=this._alphaTapMap;this.card._onAll("[data-color-swatch]","pointerdown",t=>{let a=t.currentTarget.dataset.colorSwatch;if(!a)return;let c=t.clientX,n=t.clientY,s=!1,o=m=>{let p=Math.abs(m.clientX-c),v=Math.abs(m.clientY-n);(p>ac||v>ac)&&(s=!0)},l=()=>{window.removeEventListener("pointermove",o),window.removeEventListener("pointerup",d),window.removeEventListener("pointercancel",u)},d=()=>{let m=Date.now(),p=e.get(a)||0,v=!s&&m-p<Xn;if(e.set(a,m),v){let h=this.card.shadowRoot?.querySelector(`[data-theme-alpha="${a}"]`)?.closest(".evcc-token-row")?.querySelector(`[data-theme-color-input="${a}"]`);if(h){let b=this._resolveTokenColorHex(a);b&&(h.value=b),h.click()}}l()},u=()=>{l()};window.addEventListener("pointermove",o),window.addEventListener("pointerup",d),window.addEventListener("pointercancel",u)})},i._resolveTokenColorHex=function(e){let t=this.card.shadowRoot;if(!t)return null;try{let r=document.createElement("div");r.style.cssText=`
        position: absolute;
        left: -9999px;
        width: 1px;
        height: 1px;
        background-color: var(${e});
        pointer-events: none;
      `,t.appendChild(r);let a=getComputedStyle(r).backgroundColor;return t.removeChild(r),Qn(a)}catch{return null}},i._bindThemeActions=function(){this.card._on(this.card.$("[data-action='save-theme']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t;if(e.activeThemeId)t=await this.card._actions.overwriteTheme(this.card._config.vacuum_entity_id,e.activeThemeId);else{let r=prompt("Enter a name for your new theme:");if(!r)return;t=await this.card._actions.saveThemeAsNew(this.card._config.vacuum_entity_id,r,!1)}if(t?.ok!==!1){let r=t?.active_theme_id??t?.theme_id??e.activeThemeId;this.card._state.applyThemeActivation(r,{clearDraft:!0})}await this._refreshThemeFromBackend()}),this.card._on(this.card.$("[data-action='reset-draft']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t=await this.card._actions.revertDraft(this.card._config.vacuum_entity_id);if(t?.ok!==!1){let r=t?.active_theme_id??e.activeThemeId;this.card._state.applyThemeActivation(r,{clearDraft:!0})}await this._refreshThemeFromBackend()}),this.card._onAll("[data-action='delete-preset']","click",async e=>{e.stopPropagation();let t=e.currentTarget.dataset.presetId;t&&confirm(`Delete theme "${t}"?`)&&(await this.card._actions.deleteTheme(t),await this._refreshThemeFromBackend())}),this.card._on(this.card.$("[data-action='export-theme']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t=this.card._state.effectiveActiveThemeId();if(!t){alert("No active theme to export.");return}let r=await this.card._actions.exportTheme(t);this.card._state.openThemeExportModal(JSON.stringify(r,null,2)),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='import-theme']"),"click",()=>{this.card._state.openThemeImportModal(),this.card._scheduleRender()}),this.card._on(this.card.$("[data-action='download-theme']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t=this.card._state.effectiveActiveThemeId();if(!t){alert("No active theme to download.");return}let r;try{r=await this.card._actions.exportTheme(t)}catch(m){alert(`Failed to export theme: ${m?.message??String(m)}`);return}let a=JSON.stringify(r,null,2),n=String(r?.name??r?.theme_id??t).replace(/[^\w\s.-]/g,"").trim().replace(/\s+/g,"-").toLowerCase()||"theme",s=new Date().toISOString().slice(0,10),o=`evcc-theme-${n}-${s}.json`,l=new Blob([a],{type:"application/json"}),d=URL.createObjectURL(l),u=document.createElement("a");u.href=d,u.download=o,u.style.display="none",document.body.appendChild(u),u.click(),document.body.removeChild(u),setTimeout(()=>URL.revokeObjectURL(d),0)}),this.card._on(this.card.$("[data-action='upload-theme']"),"click",()=>{let e=document.createElement("input");e.type="file",e.accept=".json,application/json",e.style.display="none",e.addEventListener("change",async t=>{let r=t.target?.files?.[0];if(!r){document.body.removeChild(e);return}try{let a=await r.text(),c=JSON.parse(a);Array.isArray(c?.scope)&&c.scope.length?await this._applyScopedThemeImport(c,`"${r.name}"`):(await this.card._actions.importTheme(c),await this._refreshThemeFromBackend(),alert(`Theme imported from ${r.name}.`))}catch(a){alert(`Failed to import "${r.name}": ${a?.message??String(a)}`)}finally{e.parentNode===document.body&&document.body.removeChild(e)}}),document.body.appendChild(e),e.click()}),this.card._on(this.card.$("[data-action='download-floor-theme']"),"click",async()=>{let e=this.card._state._ensureThemeState(),t=this.card._state.effectiveActiveThemeId();if(!t){alert("No active theme to export.");return}let a=this.card.$("[data-theme-floor-scope]")?.value;if(!a){alert("Pick a floor type to export.");return}let c;try{c=await this.card._actions.exportTheme(t)}catch(v){alert(`Failed to export theme: ${v?.message??String(v)}`);return}let n=Ua(c,[a]);if(!Wa(n)){alert(`This theme has no customised "${a}" floor settings to export. Adjust and Save the ${a} tokens first.`);return}let s=JSON.stringify(n,null,2),o=String(c?.theme?.name??"theme").replace(/[^a-z0-9._-]+/gi,"-").toLowerCase()||"theme",l=new Date().toISOString().slice(0,10),d=`evcc-floor-${a}-${o}-${l}.json`,u=new Blob([s],{type:"application/json"}),m=URL.createObjectURL(u),p=document.createElement("a");p.href=m,p.download=d,p.style.display="none",document.body.appendChild(p),p.click(),document.body.removeChild(p),setTimeout(()=>URL.revokeObjectURL(m),0)}),this.card._on(this.card.$("[data-action='apply-floor-preset']"),"click",async()=>{let e=this.card.$("[data-floor-preset]"),t=Ze.find(r=>r.id===e?.value);if(!t){alert("Pick a preset to apply.");return}await this._applyScopedThemeImport(t.envelope,`the ${t.name} preset`)})},i._refreshThemeFromBackend=async function(e={}){let t=e?.fallbackActiveThemeId??null,r=e?.fallbackDraftDirty,a=await this.card._actions.getThemeLibrary();a&&this.card._state.setThemeLibrary(a),t&&this.card._state.getActiveTheme()?.id!==t&&this.card._state._ensureThemeState().activeThemeId!==t&&this.card._state.applyThemeActivation(t,{clearDraft:r===!1}),this._autoOpenMatchingThemeGroups(),Q(this.card),this.card._scheduleRender()},i._autoOpenMatchingThemeGroups=function(){let e=this.card._state._ensureThemeState();ae.forEach(t=>{this.card._state.shouldForceThemeGroupOpenForSearch(t,ue,{excludeKeys:rc})&&(e.groupOpen[t]=!0)})}}function oc(i){i._bindMap=function(){let e=this.card.shadowRoot;if(!e)return;this._bindMapViewToggle(e),this._bindMapPolygons(e),this._bindMapTooltip(e),this._bindMapChips(e),this._bindMapConfigEntry(e),this._bindMapConfig(e),this._bindMapZoomPan(e),this._bindMapAnimal(e),this._bindMapAnimalSelect(e),(this.card._view===_.MAP_CONFIG||this.card._state.isMapViewActive?.())&&this._ensureMapSegments()},i._bindMapViewToggle=function(e){e.querySelectorAll("[data-action='set-map-view']").forEach(t=>{this.card._on(t,"click",()=>{let r=t.dataset.mapView==="true";this.card._state.setMapViewActive(r),r&&(this._syncSegmentsFromRooms(),this._ensureMapSegments()),this.card._scheduleRender()})})},i._syncSegmentsFromRooms=function(){if(!this.card._state.mapSegments().length)return;let e=this.card._state.getRoomsForActiveMap?.()??[];this.card._state.clearSegmentSelection(),[...e].filter(t=>t.enabled).sort((t,r)=>(t.order??0)-(r.order??0)).forEach(t=>this.card._state.enableSegmentForRoom(t.id))},i._bindMapPolygons=function(e){e.querySelectorAll("[data-action='toggle-segment']").forEach(t=>{let r=null;this.card._on(t,"click",a=>{if(a.stopPropagation(),this.card._mapDragOccurred){this.card._mapDragOccurred=!1;return}let c=t.dataset.segmentId;if(!c)return;if(r){clearTimeout(r),r=null;let s=this.card._state.getRoomsForActiveMap?.()??[],o=this.card._state.roomIdForSegment(c),l=o!=null?s.find(d=>String(d.id)===String(o)):null;l&&(this.card._state.openRoomEditor(l.mapId,l.id),this.card._scheduleRender());return}let n=this.card._state.isSegmentSelected(c);r=setTimeout(()=>{r=null,this.card._state.toggleSegmentSelected(c);let s=this.card._state.getRoomsForActiveMap?.()??[],o=this.card._state.roomIdForSegment(c),l=o!=null?s.find(d=>String(d.id)===String(o)):null;l&&this.card._actions.toggleRoomEnabled(l.mapId,l.id,n).then(()=>this.card._scheduleRender()).catch(d=>console.error("[eufy-vacuum-command-center] Room sync failed:",d)),this.card._scheduleRender()},220)})})},i._bindMapTooltip=function(e){let t=e.querySelector(".evcc-map-tooltip"),r=e.querySelector(".evcc-map-container");if(!t||!r)return;let a=(s,o)=>{let l=s.dataset.label??"",d=s.dataset.hint??"";t.innerHTML=`<span class="evcc-map-tooltip-label">${l}</span>`+(d?`<span class="evcc-map-tooltip-hint">${d}</span>`:""),t.classList.add("evcc-map-tooltip--visible"),c(o)},c=s=>{let o=r.getBoundingClientRect(),l=s.clientX-o.left+14,d=s.clientY-o.top-t.offsetHeight-8;t.style.left=`${Math.min(l,o.width-t.offsetWidth-8)}px`,t.style.top=`${Math.max(8,d)}px`},n=()=>t.classList.remove("evcc-map-tooltip--visible");e.querySelectorAll("[data-action='toggle-segment']").forEach(s=>{this.card._on(s,"pointerenter",o=>a(s,o)),this.card._on(s,"pointermove",o=>c(o)),this.card._on(s,"pointerleave",n),this.card._on(s,"click",n)})},i._bindMapChips=function(e){e.querySelectorAll("[data-action='map-chip-activate']").forEach(t=>{let r=null;this.card._on(t,"click",a=>{a.stopPropagation();let c=t.dataset.roomId;if(c){if(r){clearTimeout(r),r=null;let s=(this.card._state.getRoomsForActiveMap?.()??[]).find(o=>String(o.id)===String(c));s&&(this.card._state.openRoomEditor(s.mapId,s.id),this.card._scheduleRender());return}r=setTimeout(()=>{r=null},220)}})})},i._bindMapConfigEntry=function(e){e.querySelectorAll("[data-action='open-map-config']").forEach(t=>{this.card._on(t,"click",()=>{this._ensureMapSegments(),this.card.setView(_.MAP_CONFIG)})})},i._bindMapConfig=function(e){e.querySelectorAll("[data-action='map-config-back']").forEach(a=>{this.card._on(a,"click",()=>{this.card.setView(_.ROOMS)})}),e.querySelectorAll("[data-action='config-select-segment']").forEach(a=>{this.card._on(a,"click",c=>{c.stopPropagation();let n=a.dataset.segmentId;if(!n)return;let s=this.card._state.configSelectedSegmentId();this.card._state.setConfigSelectedSegmentId(s===n?null:n),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='upload-map-variant']").forEach(a=>{this.card._on(a,"click",()=>{let c=a.dataset.variant,n=document.createElement("input");n.type="file",n.accept="image/png,image/jpeg,image/webp,image/bmp";let s=async()=>{n.removeEventListener("change",s);let o=n.files?.[0];if(!o)return;let d=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.mapSegmentsData()?.map_id??null;if(!d){this.card._state.setMapActionStatus({type:"upload",variant:c,status:"error",message:"No active map found"}),this.card._scheduleRender();return}this.card._state.setMapActionStatus({type:"upload",variant:c,status:"busy"}),this.card._scheduleRender();try{let u=c.startsWith("custom"),m=await as(o,u?{maxDim:2048,allowDownscale:!0}:{allowDownscale:!1});if(!m)throw new Error("Could not prepare the image for upload");let p=m.base64,v={variant:c};if(u){let f=this.card._state.activeCustomLayoutId?.();f&&(v.layout_id=f)}await this.card._actions.uploadMapImage(d,p,v),c.startsWith("custom")||(this.card._state.setMapActionStatus({type:"analyze",variant:c,status:"busy"}),this.card._scheduleRender(),await this.card._actions.analyzeMapImage(d,{force_reanalyze:!0})),await this.card._actions.getMapSegments(d),this.card._state.clearMapActionStatus(),this.card._scheduleRender()}catch(u){console.error("[eufy-vacuum-command-center] Map upload failed:",u),this.card._state.setMapActionStatus({type:"upload",variant:c,status:"error",message:is(u)}),this.card._scheduleRender()}};n.addEventListener("change",s),n.click()})}),e.querySelectorAll("[data-action='delete-map-variant']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.variant,s=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??null;if(!(!c||!s)){if(!this.card._state.isMapVariantDeleteArmed?.(c)){this.card._state.armMapVariantDelete?.(c),this.card._scheduleRender();return}this.card._state.clearMapVariantDeleteArm?.(),this.card._state.setMapActionStatus?.({type:"delete",variant:c,status:"busy"}),this.card._scheduleRender();try{let o=await this.card._actions.deleteMapImage(s,c);await this.card._actions.getMapSegments(s),this.card._state.clearMapActionStatus?.();let l=o&&o.deleted!==!1;this.card.showToast?.(l?`${c.charAt(0).toUpperCase()}${c.slice(1)} image deleted`:`Could not delete ${c} image`,{kind:l?"success":"error"})}catch(o){console.error("[eufy-vacuum-command-center] deleteMapImage failed:",o),this.card._state.setMapActionStatus?.({type:"delete",variant:c,status:"error",message:o?.message??"Delete failed"}),this.card.showToast?.(`Could not delete ${c} image`,{kind:"error"})}this.card._scheduleRender()}})}),e.querySelectorAll("[data-action='cancel-delete-map-variant']").forEach(a=>{this.card._on(a,"click",()=>{this.card._mapVariantDeleteArmTimer&&(clearTimeout(this.card._mapVariantDeleteArmTimer),this.card._mapVariantDeleteArmTimer=null),this.card._state.clearMapVariantDeleteArm?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='analyze-map']").forEach(a=>{this.card._on(a,"click",async()=>{let n=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??null;if(n){this.card._state.setMapActionStatus({type:"analyze",status:"busy"}),this.card._scheduleRender();try{await this.card._actions.analyzeMapImage(n,{force_reanalyze:!0}),await this.card._actions.getMapSegments(n),this.card._state.clearMapActionStatus(),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] Map analysis failed:",s),this.card._state.setMapActionStatus({type:"analyze",status:"error",message:s?.message??"Analysis failed"}),this.card._scheduleRender()}}})}),e.querySelectorAll("[data-action='set-segmentation-mode']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.mode,n=this.card._state.mapSegmentsData()?.map_id??this.card._state.activeMapId?.()??null;if(!(!c||!n)&&this.card._state.segmentationMode?.()!==c)try{await this.card._actions.setSegmentationMode(n,c),await this.card._actions.getMapSegments(n),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] segmentation mode toggle failed:",s)}})});let t=()=>this.card._state.mapSegmentsData()?.map_id??this.card._state.activeMapId?.()??null;e.querySelectorAll("[data-action='set-active-custom-layout']").forEach(a=>{this.card._on(a,"click",async()=>{let c=t(),n=a.dataset.layoutId;if(!(!c||!n))try{await this.card._actions.setActiveCustomLayout(c,n),await this.card._actions.getMapSegments(c),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] set active layout failed:",s)}})}),e.querySelectorAll("[data-action='open-new-layout']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.openNewLayoutEditor(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='open-rename-layout']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.openRenameLayoutEditor(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='cancel-layout-editor']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.closeLayoutEditor(),this.card._scheduleRender()})}),e.querySelectorAll("[data-layout-field='name']").forEach(a=>{this.card._on(a,"input",()=>{this.card._state.setLayoutDraftName(a.value)})}),e.querySelectorAll("[data-action='create-layout-save']").forEach(a=>{this.card._on(a,"click",async()=>{let c=t();if(!c)return;let n=(this.card._state.layoutDraftName?.()??"").trim();try{await this.card._actions.createCustomLayout(c,n),this.card._state.closeLayoutEditor(),await this.card._actions.getMapSegments(c),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] create layout failed:",s)}})}),e.querySelectorAll("[data-action='rename-layout-save']").forEach(a=>{this.card._on(a,"click",async()=>{let c=t(),n=this.card._state.activeCustomLayoutId?.(),s=(this.card._state.layoutDraftName?.()??"").trim();if(!(!c||!n||!s))try{await this.card._actions.renameCustomLayout(c,n,s),this.card._state.closeLayoutEditor(),await this.card._actions.getMapSegments(c),this.card._scheduleRender()}catch(o){console.error("[eufy-vacuum-command-center] rename layout failed:",o)}})}),e.querySelectorAll("[data-action='delete-layout']").forEach(a=>{this.card._on(a,"click",async()=>{let c=t(),n=this.card._state.activeCustomLayoutId?.();if(!(!c||!n))try{await this.card._actions.deleteCustomLayout(c,n),await this.card._actions.getMapSegments(c),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] delete layout failed:",s)}})}),e.querySelectorAll("[data-action='compose-add']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.addComposeShape(a.dataset.shapeType||"rect"),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-select']").forEach(a=>{this.card._on(a,"click",()=>{let c=a.dataset.shapeId,n=this.card._state.composeMergeFrom?.();n&&n!==c?(this.card._state.mergeComposeShapes(n,c),this.card._state.cancelComposeMerge(),this.card._state.selectComposeShape(n)):this.card._state.selectComposeShape(c),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-deselect']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.selectComposeShape(null),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-assign-room']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.assignComposeRoom(a.dataset.shapeId,a.dataset.roomId),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-save']").forEach(a=>{this.card._on(a,"click",async()=>{let c=this.card._state.mapSegmentsData()?.map_id??this.card._state.activeMapId?.()??null;if(!c)return;let n=this.card._state.composeToSegments();if(n.length){this.card._state.setMapActionStatus?.({type:"compose-save",status:"busy"}),this.card._scheduleRender();try{let s=n.map(l=>({id:l.id,primitives:l.primitives})),o=await this.card._actions.setCustomSegments(c,s);if(!o?.saved){let l=o?.reason==="no_custom_backdrop"?"Upload a backdrop image for this layout first (Custom backdrop, below).":o?.reason?`Save failed: ${o.reason}`:"Save failed";this.card._state.setMapActionStatus?.({type:"compose-save",status:"error",message:l}),this.card._scheduleRender();return}for(let l of n)await this.card._actions.setSegmentRoomLink(c,l.id,l.room_id??null);await this.card._actions.getMapSegments(c),this.card._state.clearMapActionStatus?.(),this.card._scheduleRender()}catch(s){console.error("[eufy-vacuum-command-center] save custom segments failed:",s),this.card._state.setMapActionStatus?.({type:"compose-save",status:"error",message:s?.message??"Save failed"}),this.card._scheduleRender()}}})}),e.querySelectorAll("[data-action='compose-delete']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.deleteComposeShape(c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='compose-clear']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.clearComposeDraft(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-step']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.setComposeStep(Number(a.dataset.step??3)),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-move-scope']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.setComposeMoveScope(a.dataset.scope),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-move']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();if(!c)return;let n=this.card._state.composeStep?.()??3;this.card._state.moveComposeScoped(c,Number(a.dataset.dx??0)*n,Number(a.dataset.dy??0)*n),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-scale']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.scaleComposeShape(c,Number(a.dataset.factor??1)),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='compose-resize']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();if(!c)return;let n=this.card._state.composeStep?.()??3;this.card._state.resizeComposeShape(c,a.dataset.dim,Number(a.dataset.delta??0)*n),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-rotate']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.rotateComposeShape(c,Number(a.dataset.deg??0)),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='compose-merge-start']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.startComposeMerge(c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='compose-merge-cancel']").forEach(a=>{this.card._on(a,"click",()=>{this.card._state.cancelComposeMerge(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='compose-split']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.splitComposeShape(c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='compose-toggle-op']").forEach(a=>{this.card._on(a,"click",()=>{let c=this.card._state.composeSelectedId();c&&(this.card._state.toggleComposeOp(c),this.card._scheduleRender())})});let r=e.querySelector(".evcc-map-container--config .evcc-map-layers");r&&this.card._on(r,"click",a=>{if((this.card._state.segmentationMode?.()??"cv")!=="custom")return;if(this.card._state.composeMergeFrom?.()){this.card._state.cancelComposeMerge(),this.card._scheduleRender();return}let c=this.card._state.composeSelectedId?.();if(!c||a.target?.closest?.("[data-action='compose-select']"))return;if(this.card._mapDragOccurred){this.card._mapDragOccurred=!1;return}let n=r.getBoundingClientRect();!n.width||!n.height||(this.card._state.placeComposeScoped(c,(a.clientX-n.left)/n.width*100,(a.clientY-n.top)/n.height*100),this.card._scheduleRender())}),e.querySelectorAll("[data-action='nudge-segment']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.segmentId,n=Number(a.dataset.dx??0),s=Number(a.dataset.dy??0),l=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!(!c||!l))try{await this.card._actions.adjustMapSegment(l,c,{delta_x:n,delta_y:s}),await this.card._actions.getMapSegments(l),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(d){console.error("[eufy-vacuum-command-center] Nudge failed:",d)}})}),e.querySelectorAll("[data-action='reset-segment-adjustment']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.segmentId,s=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!c||!s)return;let o=this.card._state.mapSegments().find(m=>String(m.segment_id)===String(c));if(!o)return;let l=o.translation_offset,d=Array.isArray(l)?l[0]??0:l?.x??0,u=Array.isArray(l)?l[1]??0:l?.y??0;if(!(d===0&&u===0))try{await this.card._actions.adjustMapSegment(s,c,{delta_x:-d,delta_y:-u}),await this.card._actions.getMapSegments(s),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(m){console.error("[eufy-vacuum-command-center] Reset failed:",m)}})}),e.querySelectorAll("[data-action='adjust-edge']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.segmentId,n=a.dataset.edge,s=Number(a.dataset.delta??0),l=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!c||!l||!n)return;let d={[`edge_${n}`]:s};try{await this.card._actions.adjustMapSegment(l,c,d),await this.card._actions.getMapSegments(l),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(u){console.error("[eufy-vacuum-command-center] Edge adjust failed:",u)}})}),e.querySelectorAll("[data-action='select-vertex']").forEach(a=>{this.card._on(a,"click",c=>{c.stopPropagation();let n=Number(a.dataset.vertexIndex),s=this.card._state.configSelectedVertexIndex?.();this.card._state.setConfigSelectedVertexIndex(s===n?null:n),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='nudge-vertex']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.segmentId,n=Number(a.dataset.vertexIndex),s=Number(a.dataset.dx??0),o=Number(a.dataset.dy??0),d=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!(!c||!d))try{await this.card._actions.adjustMapSegment(d,c,{vertex_moves:[{index:n,delta_x:s,delta_y:o}]}),await this.card._actions.getMapSegments(d),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(u){console.error("[eufy-vacuum-command-center] Vertex nudge failed:",u)}})}),e.querySelectorAll("[data-action='reset-vertex']").forEach(a=>{this.card._on(a,"click",async()=>{let c=a.dataset.segmentId,n=Number(a.dataset.vertexIndex),o=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(!c||!o)return;let d=(this.card._state.mapSegments().find(u=>String(u.segment_id)===String(c))?.vertex_adjustment??[]).find(u=>u.index===n);if(!(!d||!d.delta_x&&!d.delta_y))try{await this.card._actions.adjustMapSegment(o,c,{vertex_moves:[{index:n,delta_x:-(d.delta_x??0),delta_y:-(d.delta_y??0)}]}),await this.card._actions.getMapSegments(o),this.card._state.mapSegmentsData()&&this.card._scheduleRender()}catch(u){console.error("[eufy-vacuum-command-center] Vertex reset failed:",u)}})}),e.querySelectorAll("[data-action='assign-segment-room']").forEach(a=>{this.card._on(a,"click",()=>{let c=a.dataset.segmentId,n=a.dataset.roomId;if(!c||!n)return;let s=this.card._state,o=s.roomIdForSegment(c),l=s.mapSegmentsData()?.map_id;o!=null&&String(o)===String(n)?(s.unassignSegmentRoom(c),l&&this.card._actions?.setSegmentRoomLink?.(l,c,null)):(s.assignSegmentRoom(c,n),l&&this.card._actions?.setSegmentRoomLink?.(l,c,n)),this.card._scheduleRender()})})},i._ensureMapSegments=async function(){if(this.card._state.mapSegmentsData()||this._mapSegmentsFetching)return;let t=(this.card._state.getRoomsForActiveMap?.()??[])[0]?.mapId??this.card._state.activeMapId?.()??null;if(t){this._mapSegmentsFetching=!0;try{await this.card._actions.getMapSegments(t),this.card._state.mapSegmentsData()&&(this._syncSegmentsFromRooms(),this.card._scheduleRender())}catch(r){console.error("[eufy-vacuum-command-center] Failed to load map segments:",r)}finally{this._mapSegmentsFetching=!1}}},i._bindMapAnimalSelect=function(e){e.querySelectorAll("[data-action='map-animal-select']").forEach(t=>{this.card._on(t,"change",()=>{this.card._state.setMapAnimalSelection?.(t.value),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='map-animal-toggle']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.toggleMapAnimalEnabled?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='map-texture-toggle']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.toggleMapFloorTextureEnabled?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='room-texture-toggle']").forEach(t=>{this.card._on(t,"click",()=>{this.card._state.toggleRoomFloorTextureEnabled?.(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='map-animal-scale']").forEach(t=>{this.card._on(t,"input",()=>{this.card._state.setMapAnimalScale?.(t.value);let r=e.querySelector(".evcc-map-animal"),a=r?.querySelector("animal-svg");if(r&&a){let c=parseFloat(t.value)||1,n=Math.round(64*c)+"px",s=Math.round(44*c)+"px";r.style.width=n,r.style.height=s,a.setAttribute("width",n),a.setAttribute("height",s)}}),this.card._on(t,"change",()=>{this.card._scheduleRender()})})},i._bindMapAnimal=function(e){e.querySelectorAll("[data-action='map-dot-click']").forEach(t=>{let r=e.querySelector(".evcc-map-layers");r&&this.card._on(t,"pointerdown",a=>{if(a.button!==0)return;a.stopPropagation(),a.preventDefault();let c=t.dataset.anchorKey;if(!c)return;t.setPointerCapture(a.pointerId),t.classList.add("evcc-map-animal--dragging");let n=r.getBoundingClientRect(),s=parseFloat(t.style.left)||0,o=parseFloat(t.style.top)||0,l=a.clientX-n.left-s/100*n.width,d=a.clientY-n.top-o/100*n.height,u=s,m=o,p=f=>{u=Math.max(0,Math.min(100,(f.clientX-n.left-l)/n.width*100)),m=Math.max(0,Math.min(100,(f.clientY-n.top-d)/n.height*100)),t.style.left=`${u}%`,t.style.top=`${m}%`},v=()=>{t.removeEventListener("pointermove",p),t.removeEventListener("pointerup",v),t.removeEventListener("pointercancel",v),t.classList.remove("evcc-map-animal--dragging"),this.card._state.setRoomDotAnchor?.(c,u,m);let f=this.card._state.mapSegmentsData()?.map_id;f&&c!=null&&this.card._actions?.setCompanionAnchor?.(f,c,u,m),this.card._scheduleRender()};t.addEventListener("pointermove",p),t.addEventListener("pointerup",v),t.addEventListener("pointercancel",v)})})},i._bindMapZoomPan=function(e){let t=e.querySelector(".evcc-map-container");if(!t)return;let r=()=>{let u=t.querySelector(".evcc-map-layers");if(!u)return;let m=this.card._state.mapZoom?.()??1,p=this.card._state.mapTranslateX?.()??0,v=this.card._state.mapTranslateY?.()??0;u.style.transform=`translate(${p}px,${v}px) scale(${m})`},a=u=>{let m=this.card._state.mapZoom?.()??1,p=t.getBoundingClientRect(),v=p.width/2,f=p.height/2;this.card._state.applyMapZoom?.(m*u,v,f),r(),this.card._scheduleRender?.()};e.querySelectorAll("[data-action='map-zoom-in']").forEach(u=>{this.card._on(u,"click",m=>{m.stopPropagation(),a(1.25)})}),e.querySelectorAll("[data-action='map-zoom-out']").forEach(u=>{this.card._on(u,"click",m=>{m.stopPropagation(),a(.8)})}),e.querySelectorAll("[data-action='map-zoom-fit']").forEach(u=>{this.card._on(u,"click",m=>{m.stopPropagation(),this.card._state.resetMapTransform?.(),r(),this.card._scheduleRender?.()})}),this.card._on(t,"wheel",u=>{if(!u.ctrlKey)return;u.preventDefault();let m=t.getBoundingClientRect(),p=u.clientX-m.left,v=u.clientY-m.top,f=u.deltaY<0?1.1:1/1.1,h=this.card._state.mapZoom?.()??1;this.card._state.applyMapZoom?.(h*f,p,v),r(),this.card._scheduleRender?.()},{passive:!1});let c=!1,n=0,s=0,o=!1;this.card._on(t,"pointerdown",u=>{if(u.button!==0||(this.card._mapDragOccurred=!1,u.target.closest("[data-action='map-dot-click']")))return;c=!0,o=!1,n=u.clientX,s=u.clientY;let m=v=>{if(!c)return;let f=v.clientX-n,h=v.clientY-s;n=v.clientX,s=v.clientY,!(!o&&Math.abs(f)<3&&Math.abs(h)<3)&&(o=!0,this.card._mapDragOccurred=!0,this.card._state.applyMapPan?.(f,h),r())},p=()=>{c=!1,document.removeEventListener("pointermove",m),document.removeEventListener("pointerup",p),document.removeEventListener("pointercancel",p)};document.addEventListener("pointermove",m),document.addEventListener("pointerup",p),document.addEventListener("pointercancel",p)}),this.card._on(t,"dblclick",u=>{u.target.closest("[data-action='toggle-segment']")||(this.card._state.resetMapTransform?.(),r())});let l={},d=null;this.card._on(t,"touchstart",u=>{Array.from(u.changedTouches).forEach(m=>{l[m.identifier]={x:m.clientX,y:m.clientY}}),Object.keys(l).length===2&&(u.preventDefault(),d=cc(l))},{passive:!1}),this.card._on(t,"touchmove",u=>{Array.from(u.changedTouches).forEach(b=>{l[b.identifier]={x:b.clientX,y:b.clientY}});let m=Object.values(l);if(m.length!==2||d===null)return;u.preventDefault();let p=cc(l),v=t.getBoundingClientRect(),f=(m[0].x+m[1].x)/2-v.left,h=(m[0].y+m[1].y)/2-v.top;this.card._state.applyMapZoom?.((this.card._state.mapZoom?.()??1)*(p/d),f,h),r(),d=p},{passive:!1}),this.card._on(t,"touchend",u=>{Array.from(u.changedTouches).forEach(m=>{delete l[m.identifier]}),Object.keys(l).length<2&&(d=null)})}}function cc(i){let[e,t]=Object.values(i);return Math.sqrt((e.x-t.x)**2+(e.y-t.y)**2)}var Zn=34e5;function nc(i){let e=i.length;if(!e)return 0;let t=0;return i.charCodeAt(e-1)===61&&t++,e>1&&i.charCodeAt(e-2)===61&&t++,Math.floor(e*3/4)-t}function sc(i){return new Promise((e,t)=>{let r=new FileReader;r.onerror=()=>t(r.error||new Error("FileReader failed")),r.onload=()=>{let a=String(r.result||""),c=a.indexOf(",");e(c>=0?a.slice(c+1):a)},r.readAsDataURL(i)})}async function es(i){if(typeof createImageBitmap=="function")try{let t=await createImageBitmap(i,{imageOrientation:"from-image"});return{source:t,width:t.width,height:t.height,close:()=>t.close?.()}}catch{}let e=URL.createObjectURL(i);try{let t=await new Promise((r,a)=>{let c=new Image;c.onload=()=>r(c),c.onerror=()=>a(new Error("Could not decode image file")),c.src=e});return{source:t,width:t.naturalWidth,height:t.naturalHeight,close:()=>URL.revokeObjectURL(e)}}catch(t){throw URL.revokeObjectURL(e),t}}var Be=null;async function ts(){if(Be!=null)return Be;try{let i=document.createElement("canvas");i.width=i.height=2;let e=i.getContext("2d",{alpha:!0});e.clearRect(0,0,2,2),e.fillStyle="rgba(255,0,0,1)",e.fillRect(1,1,1,1);let t=await new Promise(n=>i.toBlob(n,"image/webp",.8));if(!t||t.type!=="image/webp"||typeof createImageBitmap!="function")return Be=!1,!1;let r=await createImageBitmap(t),a=document.createElement("canvas");a.width=a.height=2;let c=a.getContext("2d",{alpha:!0});c.clearRect(0,0,2,2),c.drawImage(r,0,0),r.close?.(),Be=c.getImageData(0,0,1,1).data[3]===0}catch{Be=!1}return Be}function rs(i,e,t,r,a){let c=document.createElement("canvas");c.width=e,c.height=t;let n=c.getContext("2d",{alpha:!0});return n?(n.imageSmoothingEnabled=!0,n.imageSmoothingQuality="high",n.drawImage(i,0,0,e,t),new Promise((s,o)=>c.toBlob(l=>l?s(l):o(new Error("canvas.toBlob returned null (encode failed)")),r,a))):Promise.reject(new Error("Could not get a 2D canvas context"))}async function as(i,{maxDim:e=2048,ceilingBytes:t=Zn,allowDownscale:r=!0}={}){if(Math.ceil(i.size/3)*4<=t){let c=await sc(i),n=nc(c);if(n<=t)return{base64:c,width:null,height:null,mime:i.type||null,bytes:n}}if(!r)throw new Error("Image too large for upload. Crop or shrink this map screenshot to a smaller file, then try again.");let a=await es(i);try{let{source:c,width:n,height:s}=a;if(!n||!s)throw new Error("Decoded image has zero size (corrupt or unsupported file)");let o=await ts()?"image/webp":"image/png",l=Math.max(1,Math.floor(e)),d=.85,u=null,m=!1;for(let p=0;p<7;p++){let v=Math.min(1,l/Math.max(n,s)),f=Math.max(1,Math.round(n*v)),h=Math.max(1,Math.round(s*v)),b=await rs(c,f,h,o,o==="image/webp"?d:void 0),w=await sc(b),S=nc(w),g={base64:w,width:f,height:h,mime:o,bytes:S};if((!u||S<u.bytes)&&(u=g),v<1&&!m&&(console.warn(`[eufy-vacuum-command-center] backdrop downscaled to ${f}\xD7${h} to fit the upload limit`),m=!0),S<=t)return g;let R=Math.max(256,Math.floor(l*.8));if(o==="image/webp"&&d>.5&&(d=+(d-.1).toFixed(2)),R===l&&(o!=="image/webp"||d<=.5))break;l=R}return u}finally{a.close?.()}}function is(i){return i===3||i&&typeof i.message=="string"&&/connection lost/i.test(i.message)?"Image too large even after resizing \u2014 please pick a smaller image.":i&&i.message?i.message:"Upload failed"}function lc(i){i._bindSetup=function(){let e=this.card;e._onAll("[data-action='setup-add-vacuum']","click",async()=>{let t=e._config?.vacuum_entity_id;if(t){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let r=await e._actions.addVacuum?.(t);e._state.setSetupLastResult?.(r);let a=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(a)}catch(r){e._state.setSetupError?.(`Failed to add vacuum: ${r?.message??String(r)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-add-other-vacuum']","click",async t=>{let r=t.currentTarget?.dataset?.vacuumId;if(r){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let a=await e._actions.addVacuum?.(r);e._state.setSetupLastResult?.(a);let c=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(c)}catch(a){e._state.setSetupError?.(`Failed to add vacuum: ${a?.message??String(a)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-rename-panel-save']","click",async t=>{let r=e._config?.vacuum_entity_id;if(!r)return;let a=t.currentTarget?.closest(".evcc-setup-rename")?.querySelector(".evcc-setup-rename-input"),c=a?a.value:"";e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let n=await e._actions.renamePanel?.(r,c);e._state.setSetupLastResult?.(n);let s=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(s),e.showToast?.("Panel renamed \u2014 refresh to update the sidebar",{kind:"success"})}catch(n){e._state.setSetupError?.(`Failed to rename panel: ${n?.message??String(n)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}),e._onAll("[data-action='setup-import-map']","click",async()=>{let t=e._config?.vacuum_entity_id;if(t){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let r=await e._actions.importActiveMap?.(t);e._state.setSetupLastResult?.(r);let a=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(a);let n=(a?.vacuums?.find(s=>s.vacuum_entity_id===t)?.maps??[]).find(s=>s.imported&&!e._state.isSetupMapConfigured?.(String(s.map_id)));if(n){let s=String(n.map_id);e._state.setSetupRoomEditorLoadingMapId?.(s),e._state.setSetupError?.(null),e._scheduleRender();try{let o=await e._actions.getSetupMapRooms?.(t,s);e._state.openSetupRoomEditor?.(s,o?.rooms??[])}catch(o){e._state.setSetupError?.(`Failed to load rooms: ${o?.message??String(o)}`),e._state.setSetupRoomEditorLoadingMapId?.(null)}}}catch(r){e._state.setSetupError?.(`Failed to import map: ${r?.message??String(r)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-refresh']","click",async()=>{await e.refreshSetupStatus?.()}),e._onAll("[data-action='setup-configure-map']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!(!r||!a)){if(e._state.setupRoomEditorOpenMapId?.()===r){e._state.closeSetupRoomEditor?.(),e._scheduleRender();return}e._state.setSetupRoomEditorLoadingMapId?.(r),e._state.setSetupError?.(null),e._scheduleRender();try{let n=(await e._actions.getSetupMapRooms?.(a,r))?.rooms??[];e._state.openSetupRoomEditor?.(r,n)}catch(c){e._state.setSetupError?.(`Failed to load rooms: ${c?.message??String(c)}`),e._state.setSetupRoomEditorLoadingMapId?.(null)}e._scheduleRender()}}),e._onAll("[data-action='setup-toggle-room']","click",t=>{let r=t.currentTarget.dataset.roomId;r&&(e._state.toggleSetupRoom?.(r),e._scheduleRender())}),e._onAll("[data-action='setup-set-floor-type']","click",t=>{let r=t.currentTarget.dataset.roomId,a=t.currentTarget.dataset.floorType;!r||!a||(e._state.setSetupRoomFloorType?.(r,a),e._scheduleRender())}),e._onAll("[data-action='setup-save-rooms']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!(!r||!a)){e._state.setSetupRoomEditorSaving?.(!0),e._state.setSetupError?.(null),e._scheduleRender();try{let c=e._state.setupRoomEditorEnabledIds?.()??[],n=e._state.setupRoomEditorFloorTypesMap?.()??{};await e._actions.saveSetupRooms?.(a,r,c,n),e._state.markSetupMapConfigured?.(r),e._state.closeSetupRoomEditor?.();let s=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(s)}catch(c){e._state.setSetupError?.(`Failed to save rooms: ${c?.message??String(c)}`)}finally{e._state.setSetupRoomEditorSaving?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-delete-map-open']","click",t=>{let r=t.currentTarget.dataset.mapId,a=t.currentTarget.dataset.requiresTyped==="true";r&&(e._state.openSetupDeleteConfirm?.(r,a),e._scheduleRender())}),e._onAll("[data-action='setup-delete-map-cancel']","click",()=>{e._state.closeSetupDeleteConfirm?.(),e._scheduleRender()}),e._onAll("[data-action='setup-delete-map-input']","input",t=>{e._state.setSetupDeleteTypedToken?.(t.currentTarget.value),e._scheduleRender()}),e._onAll("[data-action='setup-delete-map-confirm']","click",async t=>{let r=t.currentTarget.dataset.mapId,a=e._config?.vacuum_entity_id;if(!r||!a)return;let n=e._state.setupDeleteStage?.()==="typing"?e._state.setupDeleteTypedToken?.():"confirmed";e._state.setSetupDeleteDeleting?.(!0),e._state.setSetupError?.(null),e._scheduleRender();try{let s=await e._actions.deleteSetupMap?.(a,r,n);if(s?.status==="success"){e._state.closeSetupDeleteConfirm?.(),e._state.setMapSegmentsData?.(null);let o=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(o),e.showToast?.("Map deleted",{kind:"success"})}else e._state.setSetupError?.(s?.message??"Failed to delete map."),e._state.setSetupDeleteDeleting?.(!1)}catch(s){e._state.setSetupError?.(`Failed to delete map: ${s?.message??String(s)}`),e._state.setSetupDeleteDeleting?.(!1),e.showToast?.("Map delete failed",{kind:"error"})}finally{e._scheduleRender()}}),e._onAll("[data-action='setup-reject-room']","click",async t=>{let r=Number(t.currentTarget.dataset.roomId),a=e._config?.vacuum_entity_id;if(!(!Number.isFinite(r)||!a)){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let c=await e._actions.rejectSetupRooms?.(a,[r]);e._state.setSetupLastResult?.(c);let n=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(n)}catch(c){e._state.setSetupError?.(`Failed to reject room: ${c?.message??String(c)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}}),e._onAll("[data-action='setup-force-remove-room']","click",async t=>{let r=Number(t.currentTarget.dataset.roomId),a=e._config?.vacuum_entity_id;if(!(!Number.isFinite(r)||!a)){e._state.setSetupLoading?.(!0),e._state.setSetupError?.(null),e._state.setSetupLastResult?.(null),e._scheduleRender();try{let c=await e._actions.forceRemoveSetupRoom?.(a,r);e._state.setSetupLastResult?.(c);let n=await e._actions.getSetupStatus?.();e._state.setSetupStatus?.(n)}catch(c){e._state.setSetupError?.(`Failed to force-remove room: ${c?.message??String(c)}`)}finally{e._state.setSetupLoading?.(!1),e._scheduleRender()}}})}}function dc(i){i._bindMappingReview=function(){this.card._onAll("[data-mrev-filter]","click",e=>{let t=e.currentTarget?.dataset?.mrevFilter;t&&(this.card._state.setMappingBoundsFilter?.(t),this.card._scheduleRender())}),this.card._onAll("[data-mrev-clear]","click",async e=>{let t=e.currentTarget?.dataset?.mrevClear;if(t){this.card._state.beginMappingBoundsClear?.(t),this.card._scheduleRender();try{await this.card._actions.clearRoomBounds?.({room_id:t}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingBoundsClear?.(),this.card._scheduleRender()}}}),this.card._onAll("[data-mrev-rebuild]","click",async e=>{let t=e.currentTarget?.dataset?.mrevRebuild;if(t){this.card._state.beginMappingRebuild?.(t),this.card._scheduleRender();try{await this.card._actions.rebuildRoomBoundsFromArchive?.({room_id:t}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingRebuild?.(),this.card._scheduleRender()}}}),this.card._onAll("[data-mrev-job-action]","click",async e=>{let t=e.currentTarget,r=t?.dataset?.mrevJobAction,a=t?.dataset?.mrevRoomId,c=t?.dataset?.mrevJobIndex;if(!(!r||!a||c==null)){this.card._state.beginMappingJobAction?.(a,Number(c),r),this.card._scheduleRender();try{r==="exclude"?await this.card._actions.excludeRoomJobBounds?.({room_id:a,job_index:Number(c)}):await this.card._actions.restoreRoomJobBounds?.({room_id:a,job_index:Number(c)}),await this.card.refreshMappingBoundsSnapshot?.()}finally{this.card._state.endMappingJobAction?.(),this.card._scheduleRender()}}})}}function uc(i){i._bindMobileShell=function(){let e=this.card;e._onAll("[data-action='mobile-more-toggle']","click",()=>{e._mobileMoreOpen=!e._mobileMoreOpen,e._scheduleRender()}),e._onAll("[data-action='mobile-more-close']","click",()=>{e._mobileMoreOpen&&(e._mobileMoreOpen=!1,e._scheduleRender())}),e._onAll("[data-action='mobile-more-select']","click",()=>{e._mobileMoreOpen&&(e._mobileMoreOpen=!1,e._scheduleRender())})}}function mc(i){i._bindExternalJobs=function(){let e=this.card;e._onAll("[data-action='set-review-subtab']","click",t=>{let r=t.currentTarget?.dataset?.subtab;e._state.setReviewSubtab(r),r==="external"&&this._refreshExternalPending(),e._scheduleRender()}),e._onAll("[data-action='open-external-wizard']","click",t=>{let r=t.currentTarget?.dataset?.pendingId,a=(e._state.externalPendingRuns()||[]).find(c=>String(c.pending_job_id)===String(r));a&&(e._state.openExternalWizard(a),e._scheduleRender())}),e._onAll("[data-action='discard-external-run']","click",async t=>{let r=t.currentTarget?.dataset?.pendingId;if(r){try{await e._actions.discardExternalRun?.(r)}catch(a){console.error("[eufy-vacuum-command-center] discard external failed:",a)}await this._refreshExternalPending(),e._scheduleRender()}}),this._externalFetchedOnce||(this._externalFetchedOnce=!0,this._refreshExternalPending())},i._refreshExternalPending=async function(){let e=this.card;try{let{pending:t,brand:r}=await e._actions.fetchExternalPendingRuns();e._state.setExternalPendingRuns(t),e._state.setExternalBrand(r),e._scheduleRender()}catch(t){console.error("[eufy-vacuum-command-center] fetch external pending failed:",t)}},i._bindExternalWizardHost=function(e){if(!e)return;let t=this.card,r=()=>t._scheduleRender();e.querySelectorAll("[data-action='close-external-wizard']").forEach(a=>{a.addEventListener("click",()=>{t._state.closeExternalWizard(),r()})}),e.querySelectorAll("[data-action='toggle-external-split']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation(),t._state.toggleExternalSplit(Number(a.dataset.order)),r()})}),e.querySelectorAll("[data-action='ext-count-inc']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation();let n=t._state.externalWizard();this._resegmentExternal({expectedRooms:(n?.segments?.length||1)+1})})}),e.querySelectorAll("[data-action='ext-count-dec']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation();let n=t._state.externalWizard();this._resegmentExternal({expectedRooms:Math.max(1,(n?.segments?.length||1)-1)})})}),e.querySelectorAll("[data-action='ext-merge-up']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation();let n=t._state.externalWizard(),s=Number(a.dataset.boundaryId),o=(n?.activeBoundaries||[]).map(Number).filter(l=>l!==s);this._resegmentExternal({activeBoundaries:o})})}),e.querySelectorAll("[data-action='ext-split-here']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation();let n=t._state.externalWizard(),s=Number(a.dataset.boundaryId),o=Array.from(new Set([...(n?.activeBoundaries||[]).map(Number),s]));this._resegmentExternal({activeBoundaries:o})})}),e.querySelectorAll("[data-action='ext-pick-room']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation(),t._state.setExternalAssignment(Number(a.dataset.order),{room_id:Number(a.dataset.roomId)}),r()})}),e.querySelectorAll("[data-action='ext-pick-room-select']").forEach(a=>{a.addEventListener("change",c=>{let n=c.target?.value;n&&(t._state.setExternalAssignment(Number(a.dataset.order),{room_id:Number(n)}),r())})}),e.querySelectorAll("[data-action='ext-set-override']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation();let n=Number(a.dataset.order),s=a.dataset.key,o=a.dataset.value;s==="clean_passes"&&(o=Number(o)),t._state.setExternalAssignmentOverride(n,s,o),r()})}),e.querySelectorAll("[data-action='ext-set-edge']").forEach(a=>{a.addEventListener("click",c=>{c.stopPropagation(),t._state.setExternalAssignment(Number(a.dataset.order),{edge_mopping:a.dataset.value==="true"}),r()})}),e.querySelectorAll("[data-action='ext-wizard-next']").forEach(a=>{a.addEventListener("click",()=>{t._state.setExternalWizardStep(2),r()})}),e.querySelectorAll("[data-action='ext-wizard-back']").forEach(a=>{a.addEventListener("click",()=>{t._state.setExternalWizardStep(1),r()})}),e.querySelectorAll("[data-action='ext-wizard-confirm']").forEach(a=>{a.addEventListener("click",()=>this._submitExternalWizard(!1))}),e.querySelectorAll("[data-action='ext-wizard-override']").forEach(a=>{a.addEventListener("click",()=>this._submitExternalWizard(!0))})},i._resegmentExternal=async function(e){let t=this.card,r=t._state.externalWizard();if(!(!r||!r.resegmentable||r.busy)){t._state.setExternalWizardBusy(!0),t._state.setExternalWizardError(null),t._scheduleRender();try{let a=await t._actions.resegmentExternalRun(r.pendingJobId,r.mapId,e);a&&a.ok?t._state.applyResegmentResult(a):t._state.setExternalWizardError("Re-segment failed \u2014 please try again.")}catch(a){console.error("[eufy-vacuum-command-center] resegment external failed:",a),t._state.setExternalWizardError("Re-segment failed: "+(a?.message||a))}finally{t._state.setExternalWizardBusy(!1),t._scheduleRender()}}},i._submitExternalWizard=async function(e){let t=this.card,r=t._state.externalWizard();if(!r)return;let c=t._state.externalWizardGroups().map(n=>{let s=n.lead||{},o=Number(s.order??0),l=r.assignments[o]||{};return{segment_orders:n.orders,room_id:l.room_id,edge_mopping:!!l.edge_mopping,override:!!e||!!l.override,overrides:l.overrides||{}}});if(c.some(n=>!n.room_id)){t._state.setExternalWizardError("Pick a room for every panel before confirming."),t._scheduleRender();return}t._state.setExternalWizardError(null),t._state.setExternalWizardBusy(!0),t._scheduleRender();try{let n=await t._actions.confirmExternalRun(r.pendingJobId,r.mapId,c);n&&n.ok?(t._state.closeExternalWizard(),await this._refreshExternalPending(),t._scheduleRender()):n&&Array.isArray(n.blocked)&&n.blocked.length?(t._state.setExternalWizardBusy(!1),t._state.setExternalWizardBlocked(n.blocked),t._scheduleRender()):(t._state.setExternalWizardBusy(!1),t._state.setExternalWizardError("Confirm failed \u2014 please try again."),t._scheduleRender())}catch(n){console.error("[eufy-vacuum-command-center] confirm external failed:",n),t._state.setExternalWizardBusy(!1),t._state.setExternalWizardError("Confirm failed: "+(n?.message||n)),t._scheduleRender()}}}var G=class{constructor(e){this.card=e}sync(e){return this.card=e,this}bindEvents(){this._bindNav(),this._bindBaseStation(),this._bindMaintenance(),this._bindMetrics(),this._bindOrder(),this._bindRunProfiles(),this._bindReview(),this._bindExternalJobs(),this._bindRooms(),this._bindRoomAccess(),this._bindRoomEstimate(),this._bindRoomEditor(),this._bindRoomRules(),this._bindThemeEditor(),this._bindMap(),this._bindSetup(),this._bindMappingReview(),this._bindMobileShell(),this._bindToasts()}_bindToasts(){this.card._onAll("[data-action='dismiss-toast']","click",e=>{let t=e.currentTarget?.dataset?.toastId;t&&(this.card._state.dismissToast?.(t),this.card._scheduleRender())})}_bindOrder(){this.bindOrderEvents(this.card.shadowRoot)}bindModalHostEvents(e){if(!e)return;let t=e.querySelector("[data-stop-propagation]");t&&t.addEventListener("click",a=>a.stopPropagation()),e.querySelectorAll("[data-action='toggle-room']").forEach(a=>{a.addEventListener("click",async c=>{c.stopPropagation();let n=Number(a.dataset.roomId),s=String(a.dataset.mapId),o=a.dataset.enabled==="true";!n||!s||(await this.card._actions.toggleRoomEnabled(s,n,o),await this.card.refreshDashboardSnapshot?.(),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='close-order-selector']").forEach(a=>{a.addEventListener("click",()=>{this.card._state.closeOrderSelector(),this.card._scheduleRender()})}),e.querySelectorAll("[data-action='set-order-position']").forEach(a=>{a.addEventListener("click",()=>{let c=Number(a.dataset.position);c&&(this.card._state.setOrderSelectorTargetPosition(c),this.card._scheduleRender())})}),e.querySelectorAll("[data-action='confirm-order-selector']").forEach(a=>{a.addEventListener("click",async()=>{try{await this.confirmOrderSelectorWithFlip()}catch(c){console.error("[eufy-vacuum-command-center] Failed to save ordered position:",c)}})}),e.querySelectorAll("[data-action='open-order-selector']").forEach(a=>{a.addEventListener("click",()=>{let c=a.dataset.scope,n=a.dataset.itemId;!c||n==null||(this.card._state.openOrderSelector(c,n),this.card._scheduleRender())})}),this._bindMaintenanceModalHost?.(e),this._bindRoomAccessHost?.(e),this._bindRoomEstimateHost?.(e),this._bindExternalWizardHost?.(e),this._bindThemeJsonModalHost?.(e),e.querySelectorAll("[data-action='close-room-editor']").forEach(a=>{a.addEventListener("click",()=>{this.card._state.closeRoomEditor(),this.card._scheduleRender()})}),e.querySelectorAll("[data-field]").forEach(a=>{a.addEventListener("click",()=>{let c=a.dataset.field,n=a.dataset.value;if(!(!c||n===void 0)){if(a.dataset.action==="apply-profile"){this.card._state.applyEditorProfile(n),this.card._scheduleRender();return}c==="clean_passes"&&(n=Number(n)),c==="edge_mopping"&&(n=n==="true"),this.card._state.updateEditorField(c,n),this.card._scheduleRender()}})});let r=e.querySelector("[data-action='save-room-editor']");r&&r.addEventListener("click",async()=>{let a=this.card._state.activeEditorRoom(),c=this.card._state.editorFields();if(!(!a||!c))try{await this.card._actions.saveRoomEditor(a.mapId,a.id,c),await this._refreshRoomEditorEstimates?.(),this.card._state.closeRoomEditor(),this.card._scheduleRender()}catch(n){console.error("[eufy-vacuum-command-center] Failed to save room editor:",n)}}),e.querySelectorAll("[data-action='save-room-profile-as-new']").forEach(a=>{a.addEventListener("click",async()=>{await this._handleSaveRoomProfileAsNew?.()})}),e.querySelectorAll("[data-action='overwrite-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleOverwriteRoomProfile?.()})}),e.querySelectorAll("[data-action='rename-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleRenameRoomProfile?.()})}),e.querySelectorAll("[data-action='delete-room-profile']").forEach(a=>{a.addEventListener("click",async()=>{a.disabled||await this._handleDeleteRoomProfile?.()})})}};fi(G.prototype);gi(G.prototype);bi(G.prototype);_i(G.prototype);yi(G.prototype);xi(G.prototype);wi(G.prototype);Si(G.prototype);Ri(G.prototype);Ei(G.prototype);ki(G.prototype);$i(G.prototype);ic(G.prototype);oc(G.prototype);lc(G.prototype);dc(G.prototype);uc(G.prototype);mc(G.prototype);function pc(i){i.callService=async function(e,t,r={},a=!1){if(!this.hass?.callService)return console.warn("[eufy-vacuum-command-center] callService called before hass was ready.",{domain:e,service:t,data:r}),null;try{let c=await this.hass.callService(e,t,r,void 0,!1,a);return a?c:void 0}catch(c){return console.error(`[eufy-vacuum-command-center] ${e}.${t} failed`,{data:r,err:c}),null}},i.callHA=async function(e,t){return this.callService("homeassistant",e,{entity_id:t})},i.callNamedService=async function(e,t={},r=!1){let a=String(e??"").trim();if(!a||!a.includes("."))return console.warn("[eufy-vacuum-command-center] Invalid full service name",{fullService:e,data:t}),null;let[c,...n]=a.split("."),s=n.join(".");return!c||!s?(console.warn("[eufy-vacuum-command-center] Invalid split service name",{fullService:e,data:t}),null):this.callService(c,s,t,r)}}var cs="get_dock_action_status",ns="wash_mop",ss="dry_mop",os="stop_dry_mop",ls="empty_dust";function vc(i){i.getDockActionStatus=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let c=await this.callService(x,cs,{vacuum_entity_id:r,map_id:String(a)},!0);return c?.response??c},i.washMop=async function(){return this._runDockAction(ns)},i.dryMop=async function(){return this._runDockAction(ss)},i.stopDryMop=async function(){return this._runDockAction(os)},i.emptyDust=async function(){return this._runDockAction(ls)},i._runDockAction=async function(e){let t=this.state?.vacuumEntityId?.(),r=this.state?.activeMapId?.();return!t||!r?null:this.callService(x,e,{vacuum_entity_id:t,map_id:String(r)})},i.getPauseTimeoutSettings=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(x,zt,{vacuum_entity_id:t},!0);return r?.response??r},i.setPauseTimeoutSettings=async function({vacuum_entity_id:e,pause_timeout_minutes_default:t}={}){let r=e??this.state?.vacuumEntityId?.();if(!r)return null;let a=await this.callService(x,Bt,{vacuum_entity_id:r,pause_timeout_minutes_default:Number(t)},!0);return a?.response??a}}var ds="run_learning_estimate",us="reanchor_learning_timeline",ms="get_next_room",ps="get_room_learning_estimates",vs="get_dashboard_snapshot",hs="get_incomplete_run_log",fs="get_trouble_rooms_log";function hc(i){i.getDashboardSnapshot=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let c=await this.callService(x,vs,{vacuum_entity_id:r,map_id:String(a)},!0);return c?.response??c},i.runLearningEstimate=async function({vacuum_entity_id:e,map_id:t,current_battery:r,started_at:a}={}){let c=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.(),s=Number.isFinite(Number(r))?Number(r):this.state?.batteryLevel?.();if(!c||!n)return null;let o={vacuum_entity_id:c,map_id:String(n),current_battery:Number.isFinite(Number(s))?Number(s):0};a&&(o.started_at=String(a));let l=await this.callService(x,ds,o,!0);return l?.response??l},i.reanchorLearningTimeline=async function({original_estimate:e,completed_rooms:t,reanchor_at:r,current_battery:a}={}){if(!e)return null;let c={original_estimate:e,completed_rooms:Array.isArray(t)?t:[],reanchor_at:r?String(r):new Date().toISOString()};if(a!=null){let s=Number(a);Number.isFinite(s)&&(c.current_battery=s)}let n=await this.callService(x,us,c,!0);return n?.response??n},i.getNextLearningRoom=async function({reanchored_estimate:e}={}){if(!e)return null;let t=await this.callService(x,ms,{reanchored_estimate:e},!0);return t?.response??t},i.getIncompleteRunLog=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(x,hs,{vacuum_entity_id:t},!0),a=r?.response??r;return!a||typeof a!="object"||!a.record_type?null:a},i.getTroubleRoomsLog=async function({vacuum_entity_id:e}={}){let t=e??this.state?.vacuumEntityId?.();if(!t)return null;let r=await this.callService(x,fs,{vacuum_entity_id:t},!0),a=r?.response??r;return!a||typeof a!="object"||!a.record_type?null:a},i.getRoomLearningEstimates=async function({vacuum_entity_id:e,map_id:t,current_battery:r}={}){let a=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.();if(!a||!c)return null;let n={vacuum_entity_id:a,map_id:String(c)};if(r!=null){let o=Number(r);Number.isFinite(o)&&(n.current_battery=o)}let s=await this.callService(x,ps,n,!0);return s?.response??s}}var gs="get_metrics_snapshot";function fc(i){i.getMetricsSnapshot=async function({vacuum_entity_id:e,room_slug:t,profile_key:r,status:a,used_for_learning:c}={}){let n=e??this.state?.vacuumEntityId?.();if(!n)return null;let s={vacuum_entity_id:n};t&&(s.room_slug=String(t)),r&&(s.profile_key=String(r)),a&&(s.status=String(a)),typeof c=="boolean"&&(s.used_for_learning=c);let o=await this.callService(x,gs,s,!0);return o?.response??o}}function gc(i){i.confirmOrderedPositionChange=async function(){let e=this.state.orderSelectorScope(),t=this.state.orderSelectorItemId(),r=this.state.orderSelectorTargetPosition(),a=this.state.getOrderAdapter(e);if(!a||t==null||r==null)return null;let c=this.state.previewMovedItemsForScope(e,t,r),n={scope:e,mode:"selector",itemId:t,targetPosition:r,patch:this.state._buildOrderPatch(c,a)};return await a.persist.call({_actions:this,state:this.state,hass:this.hass},c,n),this.state.closeOrderSelector(),{scope:e,movedItemId:t,mode:"selector"}},i.confirmDraggedOrderChange=async function(e,t){let r=this.state.getOrderAdapter(e),a=this.state.orderDragItemId();if(!r||a==null||t==null)return this.state.clearOrderDrag(),null;let c=this.state.previewDraggedItemsForScope(e,a,t),n={scope:e,mode:"drag",sourceId:a,targetId:t,patch:this.state._buildOrderPatch(c,r)};return await r.persist.call({_actions:this,state:this.state,hass:this.hass},c,n),this.state.clearOrderDrag(),{scope:e,movedItemId:a,mode:"drag"}}}function bc(i){i.getRoomProfiles=async function(){let e=await this.callService(x,jt,{},!0);return e?.response??e??null},i.saveUserRoomProfile=async function(e={}){let t=await this.callService(x,Vt,e,!0);return t?.response??t??null},i.saveRoomProfileFromRoom=async function({vacuum_entity_id:e,map_id:t,room_id:r,label:a,profile_name:c}={}){let n={vacuum_entity_id:e,map_id:t,room_id:r,label:a};c!=null&&String(c).trim()!==""&&(n.profile_name=String(c).trim());let s=await this.callService(x,qt,n,!0);return s?.response??s??null},i.overwriteRoomProfile=async function(e={}){let t=await this.callService(x,Gt,e,!0);return t?.response??t??null},i.overwriteRoomProfileFromRoom=async function({vacuum_entity_id:e,map_id:t,room_id:r,profile_name:a,label:c}={}){let n={vacuum_entity_id:e,map_id:t,room_id:r,profile_name:a};c!=null&&String(c).trim()!==""&&(n.label=String(c).trim());let s=await this.callService(x,Ut,n,!0);return s?.response??s??null},i.renameRoomProfile=async function({profile_name:e,new_profile_name:t,label:r}={}){let a={profile_name:e};t!=null&&String(t).trim()!==""&&(a.new_profile_name=String(t).trim()),r!=null&&String(r).trim()!==""&&(a.label=String(r).trim());let c=await this.callService(x,Wt,a,!0);return c?.response??c??null},i.deleteRoomProfile=async function({profile_name:e}={}){let t=await this.callService(x,Jt,{profile_name:e},!0);return t?.response??t??null},i.applyRoomProfile=async function({vacuum_entity_id:e,map_id:t,room_ids:r,profile_name:a}={}){let c=Array.isArray(r)?r.map(s=>{if(typeof s=="number")return s;let o=String(s??"").trim();if(!o)return null;let l=Number(o);return Number.isNaN(l)?o:l}).filter(s=>s!=null):[],n=await this.callService(x,Kt,{vacuum_entity_id:e,map_id:t,room_ids:c,profile_name:a},!0);return n?.response??n??null}}function _c(i){i.getSavedRunProfiles=async function({vacuum_entity_id:e,map_id:t}={}){let r=await this.callService(x,Qt,{vacuum_entity_id:e,map_id:t},!0);return r?.response??r},i.saveRunProfile=async function({vacuum_entity_id:e,map_id:t,name:r,expose_as_button:a}={}){let c=await this.callService(x,Xt,{vacuum_entity_id:e,map_id:t,name:r,expose_as_button:!!a},!0);return c?.response??c},i.overwriteRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r,name:a,expose_as_button:c}={}){let n={vacuum_entity_id:e,map_id:t,profile_id:r};a!=null&&(n.name=a),c!=null&&(n.expose_as_button=!!c);let s=await this.callService(x,Zt,n,!0);return s?.response??s},i.applyRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r}={}){let a=await this.callService(x,er,{vacuum_entity_id:e,map_id:t,profile_id:r},!0);return a?.response??a},i.renameRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r,name:a}={}){let c=await this.callService(x,tr,{vacuum_entity_id:e,map_id:t,profile_id:r,name:a},!0);return c?.response??c},i.deleteRunProfile=async function({vacuum_entity_id:e,map_id:t,profile_id:r}={}){let a=await this.callService(x,rr,{vacuum_entity_id:e,map_id:t,profile_id:r},!0);return a?.response??a}}var bs="get_learning_history_snapshot",_s="exclude_learning_job",ys="restore_learning_job";function yc(i){i.getLearningHistorySnapshot=async function({vacuum_entity_id:e,room_slug:t,profile_key:r,status:a,used_for_learning:c,limit:n}={}){let s=e??this.state?.vacuumEntityId?.();if(!s)return null;let o={vacuum_entity_id:s};t&&(o.room_slug=String(t)),r&&(o.profile_key=String(r)),a&&(o.status=String(a)),typeof c=="boolean"&&(o.used_for_learning=c),Number.isFinite(Number(n))&&(o.limit=Number(n));let l=await this.callService(x,bs,o,!0);return l?.response??l},i.excludeLearningJob=async function({vacuum_entity_id:e,job_id:t,reason:r,rebuild_csv:a=!0}={}){let c=e??this.state?.vacuumEntityId?.();if(!c||!t)return null;let n=await this.callService(x,_s,{vacuum_entity_id:c,job_id:String(t),...r?{reason:String(r)}:{},rebuild_csv:a!==!1},!0);return n?.response??n},i.restoreLearningJob=async function({vacuum_entity_id:e,job_id:t,rebuild_csv:r=!0}={}){let a=e??this.state?.vacuumEntityId?.();if(!a||!t)return null;let c=await this.callService(x,ys,{vacuum_entity_id:a,job_id:String(t),rebuild_csv:r!==!1},!0);return c?.response??c}}function xc(i){i.toggleRoomEnabled=async function(e,t,r){let a=this.state.findRoomSwitchEntityId(e,t);if(!a){console.warn(`[eufy-vacuum-command-center] Switch entity not found for room ${t} on map ${e}. Check that eufy_vacuum switch entities are loaded in HA. Available switches:`,this.state._findRoomSwitchEntities().map(c=>c.entityId));return}await this.callHA(r?"turn_off":"turn_on",a)},i.startCleaning=async function(e={}){let t=this.state.vacuumEntityId(),r=this.state.activeMapId();if(!t||!r)return;let a={vacuum_entity_id:t,map_id:r},c=await this.callService(x,Dt,a,!0),n=c?.response??c;if(n&&this.state.setStartStatus(n),n?.blocked)return this.state.clearStartConfirmation(),n;let s={vacuum_entity_id:t,map_id:r};e.confirmReducedRun&&(s.confirm_reduced_run=!0),e.confirmToken&&(s.confirm_token=e.confirmToken);let o=await this.callService(x,Ht,s,!1),l=o?.response??o??{};if(l?.started===!1&&l?.reason==="confirmation_required")return this.state.setStartConfirmation(l?.preflight??n?.preflight??n??null,l?.confirm_token??null),l;if(l?.started===!1)return this.state.clearStartConfirmation(),l;this.state.clearStartConfirmation(),this.state.clearCancelRunConfirmation();let d=await this.runLearningEstimate({vacuum_entity_id:t,map_id:r,current_battery:this.state.batteryLevel()});if(this.state.setLearningEstimate(d??null),this.state.setLearningReanchored(null),this.state.setLearningCompletedRooms([]),this.state.setLearningNextRoom(null),this.state.setLearningJobActive(!1),this.state.beginLearningJob(),this.state.learningReanchored()){let u=await this.getNextLearningRoom({reanchored_estimate:this.state.learningReanchored()});this.state.setLearningNextRoom(u&&Object.keys(u).length?u:{})}return l??{started:!0}},i.retryMissedRooms=async function(e){if(!Array.isArray(e)||e.length===0)return;let t=this.state.getRoomsForActiveMap(),r=new Set(e.map(String));await Promise.all(t.map(a=>{let c=r.has(String(a.id));return c&&!a.enabled?this.toggleRoomEnabled(a.mapId,a.id,!1):!c&&a.enabled?this.toggleRoomEnabled(a.mapId,a.id,!0):Promise.resolve()}))},i.clearQueue=async function(){let e=this.state.vacuumEntityId(),t=this.state.activeMapId();if(!e||!t)return;let r=this.state.getRoomsForActiveMap();await Promise.all(r.filter(a=>a.enabled).map(a=>this.toggleRoomEnabled(a.mapId,a.id,!0))),await this.callService(x,Ft,{vacuum_entity_id:e,map_id:t}),this.state.clearStartConfirmation(),this.state.clearCancelRunConfirmation(),this.state.clearLearningJobContext()},i.selectAllRooms=async function(){let e=this.state.getRoomsForActiveMap();await Promise.all(e.filter(t=>!t.enabled).map(t=>this.toggleRoomEnabled(t.mapId,t.id,!1)))},i.deselectAllRooms=async function(){let e=this.state.getRoomsForActiveMap();await Promise.all(e.filter(t=>t.enabled).map(t=>this.toggleRoomEnabled(t.mapId,t.id,!0)))},i.refreshRoomLearningEstimates=async function(e={}){let t=e.vacuum_entity_id??this.state.vacuumEntityId(),r=e.map_id??this.state.activeMapId();if(!t||!r)return null;let a=await this.callService(x,"get_room_learning_estimates",{vacuum_entity_id:t,map_id:r},!0),c=a?.response??a??null;return c&&this.state.setRoomEstimates?.(c),c},i.updateRoomFields=async function(e,t={}){let r=this.state.vacuumEntityId(),a=this.state.activeMapId();if(!r||!a||e==null)return null;let c={...t};(c.water_level==null||String(c.water_level).trim()==="")&&delete c.water_level,(c.profile_name==null||String(c.profile_name).trim()==="")&&delete c.profile_name;let n={vacuum_entity_id:r,map_id:a,room_id:e,...c},s=await this.callService(x,Yt,n,!0),o=s?.response??s??null;if(o)try{await this.refreshRoomLearningEstimates({vacuum_entity_id:r,map_id:a})}catch(l){console.warn("[eufy-vacuum-command-center] Failed to refresh room learning estimates after save",l)}return o},i.saveRoomEditor=async function(){let e=this.state.activeEditorRoom?.(),t=this.state.editorFields?.();if(!e||!t)return null;let r={clean_mode:t.clean_mode,fan_speed:t.fan_speed,clean_intensity:t.clean_intensity,clean_passes:t.clean_passes};return this.state.showWaterLevel()&&t.water_level!=null&&String(t.water_level).trim()!==""&&(r.water_level=t.water_level),this.state.showEdgeMopping()&&(r.edge_mopping=!!t.edge_mopping),this.updateRoomFields(e.id,r)},i.applyRoomProfile=async function(e,t){return this.updateRoomFields(e,{profile_name:t})},i.saveRoomTransition=async function(e,t){return this.updateRoomFields(e,{is_transition:t})},i.saveRoomAccess=async function(e,t,r){return this.updateRoomFields(e,{grants_access_to:t,is_dock_room:r})},i.cancelActiveRun=async function(){let e=this.state.vacuumEntityId();e&&(await this.callService("vacuum","return_to_base",{entity_id:e}),this.state.clearCancelRunConfirmation?.(),this.state.clearStartConfirmation?.())},i.persistRoomOrdering=async function(e){let t=this.state.activeMapId();!t||!Array.isArray(e)||await Promise.all(e.map(async(r,a)=>{let c=this.state.findRoomOrderNumberEntityId(t,r.id);c&&await this.callService("number","set_value",{entity_id:c,value:a+1})}))}}function wc(i){i._callThemeService=async function(e,t={}){return this.callService(x,e,t,!0)},i.getThemeLibrary=async function(){let e=await this._callThemeService(ar,{});return e?.response??e},i.setActiveTheme=async function(e,t){let r={theme_id:t};e&&(r.vacuum_entity_id=e);let a=await this._callThemeService(lr,r);return a?.response??a},i.updateWorkingDraft=async function(e,{tokens:t,colors:r,alpha:a}={}){let c={vacuum_entity_id:e};t&&Object.keys(t).length&&(c.tokens=t),r&&Object.keys(r).length&&(c.colors=r),a&&Object.keys(a).length&&(c.alpha=a);let n=await this._callThemeService(dr,c);return n?.response??n},i.revertDraft=async function(e){let t=await this._callThemeService(ur,{vacuum_entity_id:e});return t?.response??t},i.saveThemeAsNew=async function(e,t,r=!1){let a=await this._callThemeService(ir,{vacuum_entity_id:e,name:t,set_as_default:!!r});return a?.response??a},i.overwriteTheme=async function(e,t){let r=await this._callThemeService(cr,{vacuum_entity_id:e,theme_id:t});return r?.response??r},i.renameTheme=async function(e,t){let r=await this._callThemeService(nr,{theme_id:e,name:t});return r?.response??r},i.deleteTheme=async function(e){let t=await this._callThemeService(or,{theme_id:e});return t?.response??t},i.setThemeTags=async function(e,t){let r=await this._callThemeService(sr,{theme_id:e,tags:Array.isArray(t)?t:[]});return r?.response??r},i.notifyThemeExport=async function(e,t,r){let a=String(t||e||"theme").trim()||"theme",c=["Import via the card's **Upload** / **Import**, or copy the JSON:","","```json",String(r||""),"```"].join(`
`);return await this.callService("persistent_notification","create",{title:`Theme export: ${a}`,message:c,notification_id:`eufy_theme_export_${e||"theme"}`})!==null},i.exportTheme=async function(e){let t=await this._callThemeService(mr,{theme_id:e});return t?.response??t},i.importTheme=async function(e,t=null){let r={payload:e};t&&(r.vacuum_entity_id=t);let a=await this._callThemeService(pr,r);return a?.response??a}}function Sc(i){i.getMapSegments=async function(e){let t=this.state.vacuumEntityId();if(!t||!e)return;let r=await this.callService(x,gr,{vacuum_entity_id:t,map_id:e},!0),a=r?.response??r??null;if(a!=null){this.state.setMapSegmentsData(a),this.state.maybeLoadComposeDraft?.(a);try{await this._migrateLegacyMapOverlays(e,a)}catch(c){console.warn("[evcc] map overlay migration failed",c)}}},i._migrateLegacyMapOverlays=async function(e,t){let r=this.state,a=r.getLegacySegmentRoomLinks?.();if(a&&Object.keys(a).length>0){let n=new Set;for(let o of t?.segments||[])o&&o.room_id!=null&&n.add(String(o.segment_id));let s=0;for(let[o,l]of Object.entries(a))n.has(String(o))||(await this.setSegmentRoomLink(e,o,l),s+=1);r.clearLegacySegmentRoomLinks?.(),s>0&&console?.info&&console.info(`[evcc] Migrated ${s} segment-room link(s) from localStorage to backend.`)}let c=r.getLegacyDotAnchors?.();if(c&&Object.keys(c).length>0){let n=t?.companion_anchors||{},s=0;for(let[o,l]of Object.entries(c)){if(n[o])continue;let d=l?.pct_x,u=l?.pct_y;d==null||u==null||(await this.setCompanionAnchor(e,o,d,u),s+=1)}r.clearLegacyDotAnchors?.(),s>0&&console?.info&&console.info(`[evcc] Migrated ${s} companion anchor(s) from localStorage to backend.`)}},i.analyzeMapImage=async function(e,t={}){let r=this.state.vacuumEntityId();!r||!e||await this.hass.callService(x,fr,{vacuum_entity_id:r,map_id:e,...t},void 0,!0,!0)},i.uploadMapImage=async function(e,t,r={}){let a=this.state.vacuumEntityId();!a||!e||await this.hass.callService(x,vr,{vacuum_entity_id:a,map_id:e,image_base64:t,...r},void 0,!0,!0)},i.deleteMapImage=async function(e,t="default"){let r=this.state.vacuumEntityId();if(!r||!e)return null;try{let a=await this.hass.callService(x,hr,{vacuum_entity_id:r,map_id:e,variant:t},void 0,!0,!0);return a?.response??a??null}catch(a){return console.error("[eufy-vacuum-command-center] deleteMapImage failed",a),null}},i.adjustMapSegment=async function(e,t,r={}){let a=this.state.vacuumEntityId();!a||!e||await this.hass.callService(x,br,{vacuum_entity_id:a,map_id:e,segment_id:t,...r},void 0,!0,!0)},i.setSegmentRoomLink=async function(e,t,r){let a=this.state.vacuumEntityId();if(!a||!e||!t)return null;let c=await this.callService(x,Er,{vacuum_entity_id:a,map_id:e,segment_id:t,room_id:r==null?null:String(r)},!0);return c?.response??c??null},i.setCompanionAnchor=async function(e,t,r,a){let c=this.state.vacuumEntityId();if(!c||!e||t==null)return null;let n={vacuum_entity_id:c,map_id:e,room_id:String(t)};r!=null&&(n.pct_x=Number(r)),a!=null&&(n.pct_y=Number(a));let s=await this.callService(x,kr,n,!0);return s?.response??s??null},i.setSegmentationMode=async function(e,t){let r=this.state.vacuumEntityId();if(!r||!e)return null;let a=await this.callService(x,_r,{vacuum_entity_id:r,map_id:e,mode:t},!0);return a?.response??a??null},i.setCustomSegments=async function(e,t){let r=this.state.vacuumEntityId();if(!r||!e)return null;let a=await this.callService(x,yr,{vacuum_entity_id:r,map_id:e,segments:t},!0);return a?.response??a??null},i.setActiveCustomLayout=async function(e,t){let r=this.state.vacuumEntityId();if(!r||!e)return null;let a=await this.callService(x,Rr,{vacuum_entity_id:r,map_id:e,layout_id:t??null},!0);return a?.response??a??null},i.createCustomLayout=async function(e,t){let r=this.state.vacuumEntityId();if(!r||!e)return null;let a=await this.callService(x,xr,{vacuum_entity_id:r,map_id:e,name:t??""},!0);return a?.response??a??null},i.renameCustomLayout=async function(e,t,r){let a=this.state.vacuumEntityId();if(!a||!e||!t)return null;let c=await this.callService(x,wr,{vacuum_entity_id:a,map_id:e,layout_id:t,name:r??""},!0);return c?.response??c??null},i.deleteCustomLayout=async function(e,t){let r=this.state.vacuumEntityId();if(!r||!e||!t)return null;let a=await this.callService(x,Sr,{vacuum_entity_id:r,map_id:e,layout_id:t},!0);return a?.response??a??null}}function Rc(i){i.getSetupStatus=async function(){let e=await this.callService(x,Tr,{},!0);return e?.response??e??null},i.addVacuum=async function(e){let t=await this.callService(x,$r,{vacuum_entity_id:e},!0);return t?.response??t??null},i.renamePanel=async function(e,t){let r=await this.callService(x,Pr,{vacuum_entity_id:e,title:String(t??"")},!0);return r?.response??r??null},i.importActiveMap=async function(e){let t=await this.callService(x,Mr,{vacuum_entity_id:e},!0);return t?.response??t??null},i.getSetupMapRooms=async function(e,t){let r=await this.callService(x,Ar,{vacuum_entity_id:e,map_id:String(t)},!0);return r?.response??r??null},i.deleteSetupMap=async function(e,t,r){let a={vacuum_entity_id:e,map_id:String(t)};r&&(a.confirmation_token=r);let c=await this.callService(x,Ir,a,!0);return c?.response??c??null},i.saveSetupRooms=async function(e,t,r,a){let c=await this.callService(x,Cr,{vacuum_entity_id:e,map_id:String(t),enabled_room_ids:r,floor_types:a},!0);return c?.response??c??null},i.rejectSetupRooms=async function(e,t){let r=await this.callService(x,Or,{vacuum_entity_id:e,room_ids:t},!0);return r?.response??r??null},i.forceRemoveSetupRoom=async function(e,t){let r=await this.callService(x,Lr,{vacuum_entity_id:e,room_id:Number(t)},!0);return r?.response??r??null}}var xs="get_room_bounds_snapshot",ws="clear_room_bounds",Ss="exclude_room_job_bounds",Rs="restore_room_job_bounds",Es="rebuild_room_bounds_from_archive";function Ec(i){i.getMappingBoundsSnapshot=async function({vacuum_entity_id:e,map_id:t}={}){let r=e??this.state?.vacuumEntityId?.(),a=t??this.state?.activeMapId?.();if(!r||!a)return null;let c=await this.callService(x,xs,{vacuum_entity_id:r,map_id:String(a)},!0);return c?.response??c},i.clearRoomBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r}={}){let a=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.();if(!a||!c||!r)return null;let n=await this.callService(x,ws,{vacuum_entity_id:a,map_id:String(c),room_id:String(r)},!0);return n?.response??n},i.excludeRoomJobBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r,job_index:a}={}){let c=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.();if(!c||!n||!r||a==null)return null;let s=await this.callService(x,Ss,{vacuum_entity_id:c,map_id:String(n),room_id:String(r),job_index:Number(a)},!0);return s?.response??s},i.restoreRoomJobBounds=async function({vacuum_entity_id:e,map_id:t,room_id:r,job_index:a}={}){let c=e??this.state?.vacuumEntityId?.(),n=t??this.state?.activeMapId?.();if(!c||!n||!r||a==null)return null;let s=await this.callService(x,Rs,{vacuum_entity_id:c,map_id:String(n),room_id:String(r),job_index:Number(a)},!0);return s?.response??s},i.rebuildRoomBoundsFromArchive=async function({vacuum_entity_id:e,map_id:t,room_id:r}={}){let a=e??this.state?.vacuumEntityId?.(),c=t??this.state?.activeMapId?.();if(!a||!c||!r)return null;let n=await this.callService(x,Es,{vacuum_entity_id:a,map_id:String(c),room_id:String(r)},!0);return n?.response??n}}function kc(i){i.fetchExternalPendingRuns=async function(){let e=this.state?.vacuumEntityId?.();if(!e)return{pending:[],brand:null};let t=await this.callService(x,"get_external_pending_runs",{vacuum_entity_id:e},!0),r=t?.response??t;return{pending:Array.isArray(r?.pending)?r.pending:[],brand:typeof r?.brand=="string"?r.brand:null}},i.resegmentExternalRun=async function(e,t,r){let a=this.state?.vacuumEntityId?.();if(!a||!e)return{ok:!1,error:"missing_args"};let c={vacuum_entity_id:a,map_id:String(t??""),pending_job_id:e};r&&r.expectedRooms!=null?c.expected_rooms=Number(r.expectedRooms):r&&Array.isArray(r.activeBoundaries)&&(c.active_boundaries=r.activeBoundaries.map(Number));let n=await this.callService(x,"resegment_external_run",c,!0);return n?.response??n??{ok:!1}},i.confirmExternalRun=async function(e,t,r){let a=this.state?.vacuumEntityId?.();if(!a||!e)return{ok:!1,error:"missing_args"};let c=await this.callService(x,"confirm_external_run",{vacuum_entity_id:a,map_id:String(t??""),pending_job_id:e,room_assignments:Array.isArray(r)?r:[],rebuild_stats:!0},!0);return c?.response??c??{ok:!1}},i.discardExternalRun=async function(e){let t=this.state?.vacuumEntityId?.();if(!t||!e)return{ok:!1};let r=await this.callService(x,"discard_external_run",{vacuum_entity_id:t,pending_job_id:e},!0);return r?.response??r??{ok:!1}}}var X=class{constructor(e,t){this.hass=e,this.state=t}sync(e,t){return this.hass=e,this.state=t,this}};pc(X.prototype);vc(X.prototype);hc(X.prototype);fc(X.prototype);gc(X.prototype);bc(X.prototype);_c(X.prototype);yc(X.prototype);xc(X.prototype);wc(X.prototype);Sc(X.prototype);Rc(X.prototype);Ec(X.prototype);kc(X.prototype);var Tc=new WeakMap;function $c(i){i.$=function(e){return this.shadowRoot?.querySelector(e)??null},i.$all=function(e){return[...this.shadowRoot?.querySelectorAll(e)??[]]},i._on=function(e,t,r,a){if(e){if(e.dataset!==void 0){let c=`evccBound${t.charAt(0).toUpperCase()}${t.slice(1)}`;if(e.dataset[c]==="1")return;e.dataset[c]="1"}else{let c=Tc.get(e);if(c||(c=new Set,Tc.set(e,c)),c.has(t))return;c.add(t)}e.addEventListener(t,r,a)}},i._onAll=function(e,t,r,a){this.$all(e).forEach(c=>this._on(c,t,r,a))}}var it=class{constructor(e){this.card=e,this._unsubRoomCompleted=null,this._unsubRoomStarted=null,this._unsubRoomFinished=null,this._unsubJobFinished=null,this._roomEstimateRequestSeq=0,this._lastRoomEstimateMapId=null,this._lastRoomEstimateVacuumEntityId=null,this._jobProgressResetTimer=null,this._boundsExitPollTimer=null,this._jobProgress={totalEstimatedMinutes:0,completedRoomMinutes:0,currentRoomStartedAt:null,currentRoomEstimatedMinutes:0,percent:0,ticker:null}}dismissLearningSummary(){let e=this.card?._state;e&&(e.clearLearningSummary(),this.card._scheduleRender())}connect(){this._unsubRoomCompleted||this._unsubRoomStarted||this._unsubRoomFinished||this._unsubJobFinished||this._unsubRunIncomplete||!this.card?._hass?.connection?.subscribeEvents||(this._subscribeEvent("eufy_vacuum_room_completed","_unsubRoomCompleted",t=>this._handleRoomCompleted(t)),this._subscribeEvent("eufy_vacuum_room_started","_unsubRoomStarted",t=>this._handleRoomStarted(t)),this._subscribeEvent("eufy_vacuum_room_finished","_unsubRoomFinished",t=>this._handleRoomFinished(t)),this._subscribeEvent("eufy_vacuum_job_finished","_unsubJobFinished",t=>this._handleJobFinished(t)),this._subscribeEvent("eufy_vacuum_run_incomplete","_unsubRunIncomplete",t=>this._handleRunIncomplete(t)))}_subscribeEvent(e,t,r){let a=this.card?._hass;if(!a?.connection?.subscribeEvents)return;let c=a.connection.subscribeEvents(r,e);Promise.resolve(c).then(n=>{this[t]=typeof n=="function"?n:null}).catch(n=>{this[t]=null,console.warn(`[eufy-vacuum-command-center] Failed to subscribe to ${e}.`,n)})}disconnect(){typeof this._unsubRoomCompleted=="function"&&this._unsubRoomCompleted(),typeof this._unsubRoomStarted=="function"&&this._unsubRoomStarted(),typeof this._unsubRoomFinished=="function"&&this._unsubRoomFinished(),typeof this._unsubJobFinished=="function"&&this._unsubJobFinished(),typeof this._unsubRunIncomplete=="function"&&this._unsubRunIncomplete(),this._unsubRoomCompleted=null,this._unsubRoomStarted=null,this._unsubRoomFinished=null,this._unsubJobFinished=null,this._unsubRunIncomplete=null,this._stopBoundsExitPoll(),this._stopProgressTicker(),this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null)}async _handleRoomCompleted(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;if(!r||t.vacuum_entity_id!==r||!this.card?._state?.learningJobActive?.())return;let a=t.room_id,c=Number(t.duration_seconds);if(a==null||!Number.isFinite(c))return;this.card._state.pushCompletedLearningRoom({room_id:a,actual_duration_minutes:c/60}),this._jobProgress.completedRoomMinutes+=c/60,this._jobProgress.currentRoomStartedAt=Date.now();let s=(this.card._state.learningReanchored?.()?.room_timeline??this.card._state.learningEstimate?.()?.room_timeline)?.find(o=>!o.completed);this._jobProgress.currentRoomEstimatedMinutes=s?.minutes??0,await this._reanchorTimeline(),this._checkBoundsExitPolling()}async _handleRoomStarted(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(this._stopBoundsExitPoll(),await this.card?.refreshDashboardSnapshot?.(),this.card?._scheduleRender?.())}async _handleRoomFinished(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(this._stopBoundsExitPoll(),await this.card?.refreshDashboardSnapshot?.(),this._checkBoundsExitPolling(),this.card?._scheduleRender?.())}async _handleJobFinished(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;r&&t.vacuum_entity_id===r&&(await this.card?.refreshDashboardSnapshot?.(),this.card?._state?.endLearningJob?.({duration_minutes:t.duration_minutes,actual_cleaning_minutes:t.actual_cleaning_minutes,room_count:t.room_count}),this.endJobProgress(),this.card?.refreshIncompleteRunLog?.(),this.card?.refreshTroubleRoomsLog?.(),this.card?._scheduleRender?.())}async _handleRunIncomplete(e){let t=e?.data??{},r=this.card?._config?.vacuum_entity_id;if(!r||t.vacuum_entity_id!==r)return;this.card._incompleteRunLogLoaded=!1,await this.card?.refreshIncompleteRunLog?.();let a=Array.isArray(t.missed_room_ids)?t.missed_room_ids.length:this.card?._state?.incompleteRunMissedRoomIds?.()?.length??0;a>0&&this.card?.showToast?.(`Run incomplete \u2014 ${a} room${a===1?"":"s"} missed. Open Rooms to retry.`,{kind:"info",ttl:6e3}),this.card?._scheduleRender?.()}async _reanchorTimeline(){let e=this.card?._state,t=this.card?._actions;if(!e||!t)return;let r=e.learningEstimate();if(!r)return;let a=e.learningCompletedRooms(),c=e.batteryLevel(),n=await t.reanchorLearningTimeline({original_estimate:r,completed_rooms:a,reanchor_at:new Date().toISOString(),current_battery:Number.isFinite(c)?c:void 0});if(!n)return;e.setLearningReanchored(n),n?.total_minutes&&(this._jobProgress.totalEstimatedMinutes=n.total_minutes);let s=n?.room_timeline?.find(o=>!o.completed);this._jobProgress.currentRoomEstimatedMinutes=s?.minutes??0,await this._refreshNextRoom(),this.card._scheduleRender()}async _refreshNextRoom(){let e=this.card?._state,t=this.card?._actions;if(!e||!t)return;let r=e.learningReanchored();if(!r){e.setLearningNextRoom(null);return}let a=await t.getNextLearningRoom({reanchored_estimate:r});e.setLearningNextRoom(a&&Object.keys(a).length?a:{})}startJobProgress(e){if(!e)return;this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null),this._jobProgress.totalEstimatedMinutes=Number(e.total_minutes)||0,this._jobProgress.completedRoomMinutes=0,this._jobProgress.currentRoomStartedAt=Date.now();let t=e.room_timeline?.[0];this._jobProgress.currentRoomEstimatedMinutes=Number(t?.minutes)||0,this._jobProgress.percent=0,this._stopProgressTicker(),this._startProgressTicker()}endJobProgress(){this._stopProgressTicker(),this._jobProgressResetTimer&&(clearTimeout(this._jobProgressResetTimer),this._jobProgressResetTimer=null),this._jobProgress.percent=100,this.card._scheduleRender(),this._jobProgressResetTimer=setTimeout(()=>{this._jobProgress.percent=0,this._jobProgressResetTimer=null,this.card._scheduleRender()},3e3)}_checkBoundsExitPolling(){this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit?this._startBoundsExitPoll():this._stopBoundsExitPoll()}_startBoundsExitPoll(){this._boundsExitPollTimer||(this._boundsExitPollTimer=setInterval(async()=>{await this.card?.refreshDashboardSnapshot?.(),this.card?._scheduleRender?.(),this.card?._state?.dashboardJobProgress?.()?.awaiting_bounds_exit||this._stopBoundsExitPoll()},5e3))}_stopBoundsExitPoll(){this._boundsExitPollTimer&&(clearInterval(this._boundsExitPollTimer),this._boundsExitPollTimer=null)}_startProgressTicker(){this._jobProgress.ticker&&clearInterval(this._jobProgress.ticker),this._jobProgress.ticker=setInterval(()=>{this._jobProgress.percent=this._computeProgressPercent(),this.card._scheduleRender()},1e3)}_stopProgressTicker(){this._jobProgress.ticker&&(clearInterval(this._jobProgress.ticker),this._jobProgress.ticker=null)}_computeProgressPercent(){let e=this._jobProgress.totalEstimatedMinutes;if(!e||e<=0)return 0;let t=this._jobProgress.completedRoomMinutes,r=this._jobProgress.currentRoomStartedAt?Date.now()-this._jobProgress.currentRoomStartedAt:0,a=Math.max(0,r/6e4),c=Math.min(a,this._jobProgress.currentRoomEstimatedMinutes),s=(t+c)/e*100;return Math.min(Math.max(Math.floor(s),0),99)}getRoomProgressSnapshot(e){let t=this.card?._state?.learningTimelineEntryForRoom?.(e);if(t){let d=Number(t.progress_percent),u=Number(t.elapsed_minutes),m=Number(t.remaining_minutes),p=Number(t.minutes??(Number.isFinite(u)&&Number.isFinite(m)?u+m:null));if(Number.isFinite(d)||!!t.current||!!t.completed||!!t.remaining)return{isCompleted:!!t.completed,isCurrent:!!t.current,isSkipped:!!t.skipped,isRunningLong:!!t.running_long,percent:t.completed?100:Number.isFinite(d)?Math.max(0,Math.min(99,Math.floor(d))):(t.current,0),elapsedMinutes:Number.isFinite(u)?u:0,estimatedMinutes:Number.isFinite(p)?p:null,remainingMinutes:t.completed?0:Number.isFinite(m)?m:Number.isFinite(p)?p:null}}let r=this.card._state.learningReanchored?.()?.room_timeline??this.card._state.learningEstimate?.()?.room_timeline??[],a=r.find(d=>String(d.room_id)===String(e));if(!a)return null;if(a.completed){let d=Number(a.actual_duration_minutes),u=Number(a.minutes);return{isCompleted:!0,isCurrent:!1,percent:100,elapsedMinutes:Number.isFinite(d)?d:u,estimatedMinutes:Number.isFinite(u)?u:null,remainingMinutes:0}}if(r.find(d=>!d.completed)?.room_id!==a.room_id)return{isCompleted:!1,isCurrent:!1,percent:0,elapsedMinutes:0,estimatedMinutes:Number(a.minutes)||null,remainingMinutes:Number(a.minutes)||null};let n=this._jobProgress.currentRoomStartedAt?Math.max(0,(Date.now()-this._jobProgress.currentRoomStartedAt)/6e4):0,s=Number(a.minutes)||1,o=Math.min(Math.max(Math.floor(n/s*100),0),99),l=Math.max(0,s-n);return{isCompleted:!1,isCurrent:!0,percent:o,elapsedMinutes:n,estimatedMinutes:s,remainingMinutes:l}}getJobProgressPercent(){let e=Number(this.card?._state?.dashboardJobProgress?.()?.progress_percent);return Number.isFinite(e)?Math.max(0,Math.min(100,e)):this._jobProgress.percent??0}getRoomProgressPercent(e){return this.getRoomProgressSnapshot(e)?.percent??0}async loadRoomEstimates(){let e=this.card?._state,t=this.card?._actions,r=this.card?._config;if(!e||!t||!r)return;let a=String(r.vacuum_entity_id??""),c=String(e.activeMapId?.()??"");if(!a||!c)return;(this._lastRoomEstimateVacuumEntityId!==a||this._lastRoomEstimateMapId!==c)&&(e.clearRoomEstimates(),this.card._scheduleRender()),this._lastRoomEstimateVacuumEntityId=a,this._lastRoomEstimateMapId=c;let s=++this._roomEstimateRequestSeq,o=null;try{o=await t.getRoomLearningEstimates({vacuum_entity_id:a,map_id:c,current_battery:e.batteryLevel?.()})}catch(p){if(s!==this._roomEstimateRequestSeq)return;console.warn("[eufy-vacuum-command-center] Failed to load room learning estimates.",p);return}if(s!==this._roomEstimateRequestSeq||!o)return;let l=String(this.card?._config?.vacuum_entity_id??""),d=String(this.card?._state?.activeMapId?.()??""),u=String(o.vacuum_entity_id??""),m=String(o.map_id??"");l===a&&d===c&&(u&&u!==a||m&&m!==c||(e.setRoomEstimates(o),this.card._scheduleRender()))}};var ct=class i extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config=null,this._state=null,this._renderers=null,this._bindings=null,this._actions=null,this._view=_.ROOMS,this._renderScheduled=!1,this._deferredRenderTimer=null,this._startStatusTimer=null,this._dashboardSnapshotTimer=null,this._dockActionStatusTimer=null,this._pauseTimeoutSettingsTimer=null,this._metricsTimer=null,this._learningHistoryTimer=null,this._runProfilesTimer=null,this._incompleteRunLogTimer=null,this._incompleteRunLogLoaded=!1,this._troubleRoomsLogTimer=null,this._troubleRoomsLogLoaded=!1,this._themeLibrary={},this._modalHost=null,this._lastLoadedRoomEstimateMapId=null,this._lastLoadedRoomEstimateVacuumEntityId=null,this._themeLoaded=!1,this._setupStatusTimer=null,this._learningController=null,this._mobileMoreOpen=!1,this._mobileShellOverride="auto",this._boundHandleVisibilityChange=()=>this._handleVisibilityChange(),this._boundHandlePanelResume=()=>this._handlePanelResume(),this._boundHandleLocationChanged=()=>this._handlePanelResume(),this._boundHandlePageShow=e=>{e.persisted&&this._handlePanelResume()},this._boundHandleKeydown=e=>this._handleGlobalKeydown(e),this._boundHandleAnimalRegistered=()=>this._scheduleRender(),this._resizeObserver=null,this._boundHandleResize=e=>{if(!this._state||this._mobileShellOverride===!0||this._mobileShellOverride===!1)return;let t=e?.[0]?.contentRect?.width??this.getBoundingClientRect().width??window.innerWidth;this._state.setViewportFromWidth(t)&&this._scheduleRender()},$c(this)}_measureCardWidth(){let e=this.getBoundingClientRect?.();return e&&e.width>0?e.width:typeof window<"u"?window.innerWidth:1024}setConfig(e){if(!e?.vacuum_entity_id){this._config=e??{},this._renderNoVacuumPlaceholder();return}this._config=e,this._themeLibrary=e.theme_library??{},this._themeLoaded=!1,this._state?this._state.sync(this._hass,e):(this._state=new N(this._hass,e),this._state.setViewportFromWidth(this._measureCardWidth())),e.mobile_shell===!0?this._state.setViewport("mobile"):e.mobile_shell===!1&&this._state.setViewport("desktop"),this._mobileShellOverride=e.mobile_shell,this._renderers||(this._renderers=new F(this)),this._actions?this._actions.sync?.(this._hass,this._state):this._actions=new X(this._hass,this._state),this._bindings||(this._bindings=new G(this)),this._learningController||(this._learningController=new it(this)),this._scheduleRender()}set panel(e){this._panel=e,e?.config!==void 0&&this.setConfig(e.config)}_renderNoVacuumPlaceholder(){this.shadowRoot.innerHTML=`
      <style>
        :host {
          display: block;
          width: 100%;
          min-height: 100%;
          background: var(--primary-background-color, #111);
          color: var(--primary-text-color, #e6e6e6);
          font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
        }
        .evcc-setup-wrap {
          max-width: 640px;
          margin: 0 auto;
          padding: 48px 24px;
          line-height: 1.55;
        }
        .evcc-setup-title {
          font-size: 1.6em;
          font-weight: 600;
          margin: 0 0 12px 0;
        }
        .evcc-setup-lede {
          font-size: 1.05em;
          color: var(--secondary-text-color, #9aa0a6);
          margin: 0 0 24px 0;
        }
        .evcc-setup-card {
          background: var(--card-background-color, #1c2127);
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.12));
          border-radius: 12px;
          padding: 20px 22px;
          margin: 0 0 16px 0;
        }
        .evcc-setup-card h3 {
          margin: 0 0 8px 0;
          font-size: 1.05em;
          font-weight: 600;
        }
        .evcc-setup-card p, .evcc-setup-card ol {
          margin: 0 0 8px 0;
        }
        .evcc-setup-card ol {
          padding-left: 22px;
        }
        .evcc-setup-card li + li {
          margin-top: 4px;
        }
        code {
          background: rgba(255, 255, 255, 0.06);
          padding: 1px 5px;
          border-radius: 3px;
          font-size: 0.9em;
        }
        a {
          color: var(--primary-color, #3b82f6);
        }
      </style>
      <div class="evcc-setup-wrap">
        <h1 class="evcc-setup-title">Vacuum Agent \u2014 setup needed</h1>
        <p class="evcc-setup-lede">
          The integration is installed but no vacuum is configured yet, so
          the panel can't show your rooms, jobs, or controls until you
          point it at your vacuum.
        </p>
        <div class="evcc-setup-card">
          <h3>Add your vacuum</h3>
          <ol>
            <li>Open <strong>Settings \u2192 Devices &amp; Services</strong></li>
            <li>Find <strong>Vacuum Agent</strong></li>
            <li>Click <strong>Configure</strong></li>
            <li>Pick your <code>vacuum.*</code> entity from the dropdown and submit</li>
          </ol>
          <p>
            The integration will reload and this page will turn into the
            full Vacuum Agent panel with your rooms, learning history, and
            controls.
          </p>
        </div>
        <div class="evcc-setup-card">
          <h3>If you don't see a vacuum entity in the dropdown</h3>
          <p>
            This integration works on top of whatever Home Assistant
            integration provides your vacuum \u2014 make sure your vacuum is set
            up and producing a working <code>vacuum.*</code> entity first,
            then come back here and choose it.
          </p>
          <p>
            Using a Eufy vacuum? The
            <a href="https://github.com/jeppesens/eufy-clean" target="_blank" rel="noopener">eufy-clean</a>
            integration provides that entity.
          </p>
        </div>
      </div>
    `}set narrow(e){this._narrow=e}set hass(e){if(this._hass=e,!!this._config?.vacuum_entity_id){if(this._state&&this._state.sync(e,this._config),this._actions&&this._actions.sync?.(e,this._state),this._state&&!this._confirmationsWired&&(this._confirmationsWired=!0,this._state.setConfirmationsRenderTrigger?.(()=>this._scheduleRender())),this._restoreLastView(),this._state){let t=this._state.activeMapId?.();t!=null&&(this._lastSeenActiveMapId!=null&&this._lastSeenActiveMapId!==t&&(this._state.setMapSegmentsData?.(null),this._incompleteRunLogLoaded=!1),this._lastSeenActiveMapId=t)}if(this._config?.vacuum_entity_id&&this._state){let t=this._findThemeSensor(e);t?.attributes&&this._state.setBackendThemeState?.(t.attributes)}this._scheduleRender(),this._scheduleStartStatusRefresh(),this._scheduleDashboardSnapshotRefresh(),this._scheduleDockActionStatusRefresh(),this._schedulePauseTimeoutSettingsRefresh(),this._scheduleMetricsRefresh(),this._scheduleLearningHistoryRefresh(),this._scheduleRunProfilesRefresh(),this._scheduleIncompleteRunLogRefresh(),this._scheduleTroubleRoomsLogRefresh(),this._loadInitialThemeState()}}getCardSize(){return 6}static getStubConfig(){return{type:`custom:${nt}`,vacuum_entity_id:"vacuum.your_vacuum"}}_viewStorageKey(){return`evcc_last_view_${this._config?.vacuum_entity_id??"default"}`}_restoreLastView(){if(this._viewRestored)return;this._viewRestored=!0;let e;try{e=localStorage.getItem(this._viewStorageKey())}catch{e=null}e&&e!==this._view&&Object.values(_).includes(e)&&e!==_.MAPPING_ARCHIVE&&we(e,this._state)&&(this._view=e,this._scheduleRender())}setView(e){if(e===_.MAPPING_ARCHIVE&&(e=_.ROOMS),we(e,this._state)||(e=_.ROOMS),this._view!==e){this._view=e;try{localStorage.setItem(this._viewStorageKey(),String(e))}catch{}this._state?.disarmAllConfirmations?.(),this._state?.clearStartConfirmation?.(),this._state?.cancelMaintenanceResetConfirmation?.(),e===_.LEARNING_REVIEW&&this._scheduleLearningHistoryRefresh(),e===_.METRICS&&this._scheduleMetricsRefresh(),e===_.BASE_STATION&&(this._scheduleDockActionStatusRefresh(),this._schedulePauseTimeoutSettingsRefresh()),e===_.ROOMS&&this._scheduleRunProfilesRefresh(),e===_.SETUP&&this._scheduleSetupStatusRefresh(),e===_.MAPPING_REVIEW&&this._scheduleMappingBoundsRefresh(),this._scheduleRender()}}_scheduleStartStatusRefresh(){!this._state||!this._actions||(clearTimeout(this._startStatusTimer),this._startStatusTimer=setTimeout(async()=>{let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return;let r=await this._actions.callService("eufy_vacuum","get_start_status",{vacuum_entity_id:e,map_id:t},!0),a=r?.response??r;a&&this._state&&(this._state._startStatus=a,this._scheduleRender())},800))}async refreshDashboardSnapshot(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getDashboardSnapshot({vacuum_entity_id:e,map_id:t});if(!r||!this._state)return null;this._state.setDashboardSnapshot?.(r);let a=r?.job_control??r?.start_status??null;return a&&(this._state._startStatus=a),this._scheduleRender(),r}_scheduleDashboardSnapshotRefresh(){!this._state||!this._actions||(clearTimeout(this._dashboardSnapshotTimer),this._dashboardSnapshotTimer=setTimeout(()=>{this.refreshDashboardSnapshot()},500))}async refreshDockActionStatus(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getDockActionStatus({vacuum_entity_id:e,map_id:t});return!r||!this._state?null:(this._state.setDockActionStatus?.(r),this._scheduleRender(),r)}async refreshPauseTimeoutSettings(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getPauseTimeoutSettings({vacuum_entity_id:e});return this._state.setPauseTimeoutSettings?.(t),this._scheduleRender(),t}_schedulePauseTimeoutSettingsRefresh(){!this._state||!this._actions||(clearTimeout(this._pauseTimeoutSettingsTimer),this._pauseTimeoutSettingsTimer=setTimeout(()=>{this.refreshPauseTimeoutSettings()},350))}_scheduleDockActionStatusRefresh(){!this._state||!this._actions||(clearTimeout(this._dockActionStatusTimer),this._dockActionStatusTimer=setTimeout(()=>{this.refreshDockActionStatus()},600))}async refreshMetricsSnapshot(){if(!this._state||!this._actions)return null;let e=this._state.metricsFilters?.()??{},t=await this._actions.getMetricsSnapshot({vacuum_entity_id:this._state.vacuumEntityId?.(),room_slug:e.room_slug||void 0,profile_key:e.profile_key||void 0,status:e.status||void 0,used_for_learning:e.used_for_learning==="true"?!0:e.used_for_learning==="false"?!1:void 0});return!t||!this._state?null:(this._state.setMetricsSnapshot?.(t),this._scheduleRender(),t)}_scheduleMetricsRefresh(){!this._state||!this._actions||this._view===_.METRICS&&(clearTimeout(this._metricsTimer),this._metricsTimer=setTimeout(()=>{this.refreshMetricsSnapshot()},500))}async refreshLearningHistorySnapshot(){if(!this._state||!this._actions)return null;let e=this._state.learningHistoryFilters?.()??{},t=await this._actions.getLearningHistorySnapshot({vacuum_entity_id:this._state.vacuumEntityId?.(),room_slug:e.room_slug||void 0,profile_key:e.profile_key||void 0,status:e.status||void 0,used_for_learning:e.used_for_learning==="true"?!0:e.used_for_learning==="false"?!1:void 0,limit:e.limit});return!t||!this._state?null:(this._state.setLearningHistorySnapshot?.(t),this._scheduleRender(),t)}_scheduleLearningHistoryRefresh(){!this._state||!this._actions||this._view===_.LEARNING_REVIEW&&(clearTimeout(this._learningHistoryTimer),this._learningHistoryTimer=setTimeout(()=>{this.refreshLearningHistorySnapshot()},500))}async refreshMappingBoundsSnapshot(){if(!this._state||!this._actions)return null;let e=await this._actions.getMappingBoundsSnapshot?.();return!e||!this._state?null:(this._state.setMappingBoundsSnapshot?.(e),this._scheduleRender(),e)}_scheduleMappingBoundsRefresh(){!this._state||!this._actions||this._view===_.MAPPING_REVIEW&&(clearTimeout(this._mappingBoundsTimer),this._mappingBoundsTimer=setTimeout(()=>{this.refreshMappingBoundsSnapshot()},500))}async refreshRunProfiles(){if(!this._state||!this._actions||this._view!==_.ROOMS)return null;let e=this._state.vacuumEntityId(),t=this._state.activeMapId();if(!e||!t)return null;let r=await this._actions.getSavedRunProfiles({vacuum_entity_id:e,map_id:t});return this._state.setRunProfilesLibrary?.(r),this._scheduleRender(),r}async refreshRoomProfiles(){if(!this._state||!this._actions)return null;let e=await this._actions.getRoomProfiles();return e?(this._state.setRoomProfilesLibrary?.(e),this._scheduleRender(),e):null}_scheduleRunProfilesRefresh(){!this._state||!this._actions||this._view===_.ROOMS&&(clearTimeout(this._runProfilesTimer),this._runProfilesTimer=setTimeout(()=>{this.refreshRunProfiles()},450))}async refreshIncompleteRunLog(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getIncompleteRunLog?.({vacuum_entity_id:e});return this._incompleteRunLogLoaded=!0,this._state?(this._state.setIncompleteRunLog?.(t??null),this._scheduleRender(),t):null}_scheduleIncompleteRunLogRefresh(){!this._state||!this._actions||this._incompleteRunLogLoaded||(clearTimeout(this._incompleteRunLogTimer),this._incompleteRunLogTimer=setTimeout(()=>{this.refreshIncompleteRunLog()},1200))}async refreshTroubleRoomsLog(){if(!this._state||!this._actions)return null;let e=this._state.vacuumEntityId();if(!e)return null;let t=await this._actions.getTroubleRoomsLog?.({vacuum_entity_id:e});return this._troubleRoomsLogLoaded=!0,this._state?(this._state.setTroubleRoomsLog?.(t??null),this._scheduleRender(),t):null}_scheduleTroubleRoomsLogRefresh(){!this._state||!this._actions||this._troubleRoomsLogLoaded||(clearTimeout(this._troubleRoomsLogTimer),this._troubleRoomsLogTimer=setTimeout(()=>{this.refreshTroubleRoomsLog()},1400))}async refreshSetupStatus(){if(!(!this._state||!this._actions)){this._state.setSetupLoading?.(!0),this._scheduleRender();try{let e=await this._actions.getSetupStatus?.();e&&this._state&&this._state.setSetupStatus?.(e)}finally{this._state.setSetupLoading?.(!1),this._scheduleRender()}}}_scheduleSetupStatusRefresh(){!this._state||!this._actions||this._view===_.SETUP&&(clearTimeout(this._setupStatusTimer),this._setupStatusTimer=setTimeout(()=>{this.refreshSetupStatus()},400))}_findThemeSensor(e){let t=this._config?.vacuum_entity_id;if(!t||!e)return null;let a=`sensor.${t.split(".")[1]}_theme_state`;return e.states[a]?e.states[a]:Object.values(e.states).find(c=>c.entity_id.startsWith("sensor.")&&c.entity_id.includes("_theme_state")&&c.attributes?.vacuum_entity_id===t)??null}async _loadInitialThemeState(){if(this._themeLoaded||!this._actions||!this._hass||!this._config?.vacuum_entity_id)return;let t=this._findThemeSensor(this._hass);t?.attributes&&this._state.setBackendThemeState?.(t.attributes);let r=await this._actions.getThemeLibrary();r&&this._state.setThemeLibrary?.(r),this._themeLoaded=!0,Q(this),this._scheduleRender()}_scheduleRender(){this._renderScheduled||(this._renderScheduled=!0,Promise.resolve().then(()=>{this._renderScheduled=!1,this._render()}))}showToast(e,t={}){if(!this._state?.pushToast)return null;let r=this._state.pushToast(e,t);this._scheduleRender();let a=Number.isFinite(t?.ttl)?Math.max(1e3,t.ttl):3500;return setTimeout(()=>{this._scheduleRender()},a+80),r}_scheduleDeferredRender(){this._deferredRenderTimer&&window.clearTimeout(this._deferredRenderTimer),this._deferredRenderTimer=window.setTimeout(()=>{this._deferredRenderTimer=null,this._scheduleRender()},600)}_render(){if(!this._config||!this._hass||!this._state||!this._renderers)return;Q(this),this._maybeLoadRoomEstimates(),this._mobileShellOverride!==!0&&this._mobileShellOverride!==!1&&this._state.setViewportFromWidth?.(this._measureCardWidth()),we(this._view??_.ROOMS,this._state)||(this._view=_.ROOMS);let e=oi(this),t=this._captureShadowFocusState(),r=this._captureShadowScrollState(),a=this._ensureShellFrame(Zi),c=this._state.isMobileViewport?.()??!1,n=this.shadowRoot.querySelector(".evcc-shell");n&&(n.dataset.viewport=c?"mobile":"desktop");let s=c?this._renderers.renderMobileHeader?.(e)??"":li(e),o;try{o=di(e)}catch(m){console.error("[eufy-vacuum-command-center] renderView threw for view:",e.view,m),o=`<div class="evcc-empty">View error \u2014 check console (${e.view})</div>`}let l=c?this._renderers.renderMobileBottomNav?.(e)??"":"",d=c?this._renderers.renderMobileOverlay?.(e)??"":"";a.header.dataset.renderedHtml!==s&&(a.header.innerHTML=s,a.header.dataset.renderedHtml=s),a.bottomNav&&a.bottomNav.dataset.renderedHtml!==l&&(a.bottomNav.innerHTML=l,a.bottomNav.dataset.renderedHtml=l),a.mobileOverlay&&a.mobileOverlay.dataset.renderedHtml!==d&&(a.mobileOverlay.innerHTML=d,a.mobileOverlay.dataset.renderedHtml=d),this._updateToastHost(e),a.viewStage.dataset.view=e.view,Object.entries(a.viewRoots).forEach(([m,p])=>{let v=m===e.view;p.hidden=!v,p.setAttribute("aria-hidden",v?"false":"true")});let u=a.viewRoots[e.view];u&&u.dataset.renderedHtml!==o&&(u.innerHTML=o,u.dataset.renderedHtml=o),this._updateModalHost(),this._bindings?.bindEvents(),this._restoreShadowFocusState(t),this._restoreShadowScrollState(r)}_ensureShellFrame(e){let t=this.shadowRoot?.querySelector("[data-evcc-style-root]"),r=this.shadowRoot?.querySelector("[data-evcc-header-root]"),a=this.shadowRoot?.querySelector("[data-evcc-view-stage]"),c=this.shadowRoot?.querySelector("[data-evcc-bottom-nav-root]"),n=this.shadowRoot?.querySelector("[data-evcc-mobile-overlay-root]"),s=this._collectViewRoots();return!t||!r||!a||!c||!n||Object.keys(s).length!==at.length?(this.shadowRoot.innerHTML=`
        <style data-evcc-style-root>${e}</style>

        <ha-card>
          <div class="evcc-shell">
            <div data-evcc-header-root></div>
            <div class="evcc-view-stage" data-evcc-view-stage data-view="${this._view??_.ROOMS}">
              ${at.map(l=>`
                <div
                  class="evcc-view-root"
                  data-evcc-view-root="${l}"
                  ${l===(this._view??_.ROOMS)?"":"hidden"}
                  aria-hidden="${l===(this._view??_.ROOMS)?"false":"true"}"
                ></div>
              `).join("")}
            </div>
            <div data-evcc-bottom-nav-root></div>
            <div data-evcc-mobile-overlay-root></div>
          </div>
        </ha-card>
      `,t=this.shadowRoot?.querySelector("[data-evcc-style-root]"),r=this.shadowRoot?.querySelector("[data-evcc-header-root]"),a=this.shadowRoot?.querySelector("[data-evcc-view-stage]"),c=this.shadowRoot?.querySelector("[data-evcc-bottom-nav-root]"),n=this.shadowRoot?.querySelector("[data-evcc-mobile-overlay-root]"),s=this._collectViewRoots()):t.textContent!==e&&(t.textContent=e),{styleRoot:t,header:r,viewStage:a,bottomNav:c,mobileOverlay:n,viewRoots:s}}_collectViewRoots(){return this.shadowRoot?at.reduce((e,t)=>{let r=this.shadowRoot.querySelector(`[data-evcc-view-root="${t}"]`);return r instanceof HTMLElement&&(e[t]=r),e},{}):{}}_updateModalHost(){let e={state:this._state,renderers:this._renderers},t=typeof this._renderers.renderRoomEditorModal=="function"?this._renderers.renderRoomEditorModal(e):"",r=typeof this._renderers.renderRoomAccessModal=="function"?this._renderers.renderRoomAccessModal(e):"",a=typeof this._renderers.renderRoomEstimateModal=="function"?this._renderers.renderRoomEstimateModal(e):"",c=typeof this._renderers.renderOrderSelectorModal=="function"?this._renderers.renderOrderSelectorModal(e):"",n=typeof this._renderers.renderMaintenanceItemModal=="function"?this._renderers.renderMaintenanceItemModal(e):"",s=typeof this._renderers.renderExternalWizardModal=="function"?this._renderers.renderExternalWizardModal(e):"",o=typeof this._renderers.renderThemeJsonModal=="function"?this._renderers.renderThemeJsonModal(e):"",l=`${t}${r}${a}${c}${n}${s}${o}`;if(!l){this._modalHost&&(this._modalHost.remove(),this._modalHost=null);return}this._modalHost||(this._modalHost=document.createElement("div"),this._modalHost.className="evcc-modal-host",document.body.appendChild(this._modalHost));let d=`<style>${ec}</style>${l}`;if(this._modalHost.dataset.renderedHtml!==d){let u=Array.from(this._modalHost.querySelectorAll(".evcc-modal-body"),p=>p.scrollTop);this._modalHost.innerHTML=d,this._modalHost.dataset.renderedHtml=d;let m=this._modalHost.querySelectorAll(".evcc-modal-body");u.forEach((p,v)=>{p&&m[v]&&(m[v].scrollTop=p)})}this._bindings?.bindModalHostEvents(this._modalHost)}_handleGlobalKeydown(e){if(e?.key!=="Escape"||!this._modalHost||!this._state)return;let t=[["maintenance","activeMaintenanceModalItem","closeMaintenanceModal"],["room-estimate","isRoomEstimateModalOpen","closeRoomEstimateModal"],["room-access","isRoomAccessOpen","closeRoomAccess"],["order","isOrderSelectorOpen","closeOrderSelector"],["room-editor","isRoomEditorOpen","closeRoomEditor"]];for(let[,r,a]of t){let c=this._state[r],n=this._state[a];if(!(typeof c!="function"||typeof n!="function")&&c.call(this._state)){n.call(this._state),this._scheduleRender(),e.preventDefault();return}}}_updateToastHost(e){let t=this._renderers.renderToasts?.(e)??"";if(!t){this._toastHost&&(this._toastHost.remove(),this._toastHost=null);return}this._toastHost||(this._toastHost=document.createElement("div"),this._toastHost.className="evcc-toast-host",document.body.appendChild(this._toastHost));let r=`<style>${tc}</style>${t}`;this._toastHost.dataset.renderedHtml!==r&&(this._toastHost.innerHTML=r,this._toastHost.dataset.renderedHtml=r),this._toastHost.querySelectorAll("[data-action='dismiss-toast']").forEach(a=>{a.dataset.evccBoundClick!=="1"&&(a.dataset.evccBoundClick="1",a.addEventListener("click",()=>{let c=a.dataset.toastId;c&&(this._state.dismissToast?.(c),this._scheduleRender())}))})}connectedCallback(){this._learningController?.connect(),this._loadAnimalSvg(),document.addEventListener("visibilitychange",this._boundHandleVisibilityChange),window.addEventListener("focus",this._boundHandlePanelResume),window.addEventListener("location-changed",this._boundHandleLocationChanged),window.addEventListener("pageshow",this._boundHandlePageShow),document.addEventListener("keydown",this._boundHandleKeydown),document.addEventListener("animal-svg-registered",this._boundHandleAnimalRegistered),this._state&&this._state.setViewportFromWidth(this._measureCardWidth()),typeof ResizeObserver<"u"&&(this._resizeObserver=new ResizeObserver(this._boundHandleResize),this._resizeObserver.observe(this)),this._scheduleRender()}_loadAnimalSvg(){i._animalSvgLoaded||(i._animalSvgLoaded=!0,import("/eufy_vacuum/frontend/animal-svg/manifest.js").then(()=>this._scheduleRender()).catch(e=>console.warn("[eufy-vacuum-command-center] animal-svg load failed:",e)))}disconnectedCallback(){document.removeEventListener("visibilitychange",this._boundHandleVisibilityChange),window.removeEventListener("focus",this._boundHandlePanelResume),window.removeEventListener("location-changed",this._boundHandleLocationChanged),window.removeEventListener("pageshow",this._boundHandlePageShow),document.removeEventListener("keydown",this._boundHandleKeydown),document.removeEventListener("animal-svg-registered",this._boundHandleAnimalRegistered),this._resizeObserver&&(this._resizeObserver.disconnect(),this._resizeObserver=null),this._modalHost&&(this._modalHost.remove(),this._modalHost=null),this._toastHost&&(this._toastHost.remove(),this._toastHost=null),this._learningController?.disconnect(),clearTimeout(this._startStatusTimer),clearTimeout(this._dashboardSnapshotTimer),clearTimeout(this._dockActionStatusTimer),clearTimeout(this._pauseTimeoutSettingsTimer),clearTimeout(this._metricsTimer),clearTimeout(this._learningHistoryTimer),clearTimeout(this._runProfilesTimer),clearTimeout(this._setupStatusTimer),clearTimeout(this._deferredRenderTimer),this._deferredRenderTimer=null}_handleVisibilityChange(){document.visibilityState==="visible"&&this._handlePanelResume()}_handlePanelResume(){this.offsetHeight,this._scheduleRender(),this._scheduleDashboardSnapshotRefresh(),this._scheduleStartStatusRefresh()}_maybeLoadRoomEstimates(){let e=this._state,t=this._learningController,r=this._config;if(!e||!t||!r)return;let a=String(e.activeMapId?.()??""),c=String(r.vacuum_entity_id??"");if(!a||!c||this._view!==_.ROOMS)return;let n=a===String(this._lastLoadedRoomEstimateMapId??""),s=c===String(this._lastLoadedRoomEstimateVacuumEntityId??"");n&&s||(t.loadRoomEstimates(),this._lastLoadedRoomEstimateMapId=a,this._lastLoadedRoomEstimateVacuumEntityId=c)}_captureShadowFocusState(){let e=this._getDeepActiveElement();if(!(e instanceof HTMLElement))return null;let t=this._buildFocusRestoreSelector(e);if(!t)return null;let r=e instanceof HTMLInputElement||e instanceof HTMLTextAreaElement;return{selector:t,selectionStart:r?e.selectionStart:null,selectionEnd:r?e.selectionEnd:null,selectionDirection:r?e.selectionDirection:null}}_getDeepActiveElement(){let e=document.activeElement;for(;e?.shadowRoot?.activeElement;)e=e.shadowRoot.activeElement;if(e instanceof HTMLElement&&this.shadowRoot?.contains(e))return e;let t=this.shadowRoot?.activeElement;return t instanceof HTMLElement?t:null}_restoreShadowFocusState(e){if(!e?.selector||!this.shadowRoot)return;let t=this.shadowRoot.querySelector(e.selector);if(!(!(t instanceof HTMLElement)||(t.focus({preventScroll:!0}),!(t instanceof HTMLInputElement||t instanceof HTMLTextAreaElement)))&&!(e.selectionStart==null||e.selectionEnd==null))try{t.setSelectionRange(e.selectionStart,e.selectionEnd,e.selectionDirection??"none")}catch{}}_buildFocusRestoreSelector(e){let t=["data-theme-search","data-theme-group-search","data-theme-token","data-theme-color-input","data-theme-alpha","data-rule-input","data-rule-select","data-rule-number-input","data-theme-modified-only","data-room-id","data-rule-id"];for(let r of t){if(!e.hasAttribute(r))continue;let a=e.getAttribute(r),c=String(e.tagName||"").toLowerCase(),n=e.getAttribute("type"),s=n?`[type="${CSS.escape(n)}"]`:"",o=Array.from(e.classList||[]).filter(Boolean).map(l=>`.${CSS.escape(l)}`).join("");return a==null||a===""?`${c}[${r}]${s}${o}`:`${c}[${r}="${CSS.escape(a)}"]${s}${o}`}return e.id?`#${CSS.escape(e.id)}`:null}_captureShadowScrollState(){return this.shadowRoot?[".evcc-view-stage",".evcc-theme-editor-scrollbox",".evcc-room-rules-content",".evcc-rule-editor-body",".evcc-rule-entity-search"].flatMap(t=>Array.from(this.shadowRoot.querySelectorAll(t)).map((r,a)=>({selector:t,index:a,scrollTop:r.scrollTop,scrollLeft:r.scrollLeft}))):[]}_restoreShadowScrollState(e=[]){!this.shadowRoot||!Array.isArray(e)||!e.length||e.forEach(t=>{let a=this.shadowRoot.querySelectorAll(t.selector)?.[t.index];a instanceof HTMLElement&&(a.scrollTop=t.scrollTop??0,a.scrollLeft=t.scrollLeft??0)})}};ct._animalSvgLoaded=!1;customElements.define(nt,ct);var Mc="eufy-room-card",Nt="eufy-room-card-editor",Lt=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config={}}setConfig(e){this._config=e??{},this._render()}set hass(e){this._hass=e,this._render()}_vacuumEntities(){return this._hass?Object.keys(this._hass.states).filter(e=>e.startsWith("vacuum.")).sort():[]}_roomSwitchesFor(e){return!this._hass||!e?[]:Object.entries(this._hass.states).filter(([t,r])=>t.startsWith("switch.")&&r.attributes?.vacuum_entity_id===e&&r.attributes?.room_id!=null).map(([,t])=>({room_id:t.attributes.room_id,room_name:t.attributes.room_name??t.attributes.friendly_name??`Room ${t.attributes.room_id}`})).sort((t,r)=>String(t.room_name).localeCompare(String(r.room_name)))}_fire(e){!e?.vacuum_entity_id||e?.room_id==null||this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:e},bubbles:!0,composed:!0}))}_render(){let e=this._vacuumEntities(),t=this._config.vacuum_entity_id??"",r=this._roomSwitchesFor(t),a=this._config.room_id!=null?String(this._config.room_id):"",c=this._config.name??"";this.shadowRoot.innerHTML=`
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
          ${e.map(n=>`<option value="${me(n)}" ${n===t?"selected":""}>${me(n)}</option>`).join("")}
        </select>
      </div>

      <div class="field">
        <label>Room</label>
        ${t?r.length===0?`<div class="no-rooms">No room switches found for ${me(t)}.</div>`:`<select id="room">
               <option value="" disabled ${a?"":"selected"}>\u2014 pick a room \u2014</option>
               ${r.map(n=>`<option value="${me(String(n.room_id))}" ${String(n.room_id)===a?"selected":""}>${me(n.room_name)}</option>`).join("")}
             </select>`:'<div class="hint">Select a vacuum first.</div>'}
      </div>

      <div class="field">
        <label>Name override <span style="font-weight:400;text-transform:none">(optional)</span></label>
        <input id="name" type="text" placeholder="Leave blank to use room name" value="${me(c)}">
        <div class="hint">Overrides the label shown on the card.</div>
      </div>
    `,this.shadowRoot.getElementById("vacuum")?.addEventListener("change",n=>{this._fire({...this._config,vacuum_entity_id:n.target.value,room_id:void 0})}),this.shadowRoot.getElementById("room")?.addEventListener("change",n=>{let s=n.target.value,o=Number(s);this._fire({...this._config,room_id:Number.isFinite(o)?o:s})}),this.shadowRoot.getElementById("name")?.addEventListener("change",n=>{let s=n.target.value.trim(),o={...this._config};s?o.name=s:delete o.name,this._fire(o)})}static getConfigElement(){return document.createElement(Nt)}static getStubConfig(e){let t=e?.states??{},r=Object.keys(t).find(c=>c.startsWith("vacuum."))??"",a=Object.entries(t).find(([c,n])=>c.startsWith("switch.")&&n.attributes?.vacuum_entity_id===r&&n.attributes?.room_id!=null);return{vacuum_entity_id:r,room_id:a?.[1]?.attributes?.room_id??null}}};customElements.define(Nt,Lt);var Pt=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config=null,this._fields=null,this._saving=!1,this._starting=!1}setConfig(e){this._config=e??{},this._fields=null,this._render()}set hass(e){this._hass=e,this._render()}_objectId(){return(this._config?.vacuum_entity_id??"").split(".")[1]??""}_allRoomSwitches(){let{states:e}=this._hass??{},t=this._config?.vacuum_entity_id;return!e||!t?[]:Object.entries(e).filter(([r,a])=>r.startsWith("switch.")&&a.attributes?.vacuum_entity_id===t&&a.attributes?.room_id!=null).map(([r,a])=>({entityId:r,state:a.state,attrs:a.attributes??{}}))}_targetSwitch(){let e=String(this._config?.room_id??"");return this._allRoomSwitches().find(t=>String(t.attrs.room_id)===e)??null}_adapterOptions(e){let r=this._targetSwitch()?.attrs?.[e];return Array.isArray(r)?r:[]}_cleanModeOptions(){return this._adapterOptions("clean_mode_options")}_suctionOptions(){return this._adapterOptions("fan_speed_options")}_waterLevelOptions(){return this._adapterOptions("water_level_options")}_cleanIntensityOptions(e,t){return this._adapterOptions("clean_intensity_options")}_isMopMode(e){return String(e??"").toLowerCase().replace(/[\s_-]/g,"").includes("mop")}_committedFields(){let e=this._targetSwitch()?.attrs??{};return{clean_mode:e.clean_mode??"vacuum",fan_speed:e.fan_speed??null,water_level:e.water_level??null,clean_intensity:e.clean_intensity??null,clean_passes:Number(e.clean_passes??1),edge_mopping:!!(e.edge_mopping??!1)}}_currentFields(){return this._fields??this._committedFields()}_isDirty(){if(!this._fields)return!1;let e=this._committedFields();return Object.keys(this._fields).some(t=>this._fields[t]!==e[t])}_setField(e,t){this._fields={...this._currentFields(),[e]:t},this._render()}_render(){if(!this._config?.vacuum_entity_id||this._config?.room_id==null){this.shadowRoot.innerHTML="";return}let e=this._targetSwitch(),t=e?.attrs??{},r=e?.state==="on",a=this._config.name??t.room_name??`Room ${this._config.room_id}`,c=t.slug??"",n=String(t.map_id??""),s=!!(t.carpet??!1),o=this._currentFields(),l=this._isDirty(),d=this._isMopMode(o.clean_mode),u=this._cleanModeOptions(),m=this._suctionOptions(),p=d&&!s?this._waterLevelOptions():[],v=this._cleanIntensityOptions(c,n),f=d&&!s,h=(g,R,y,T)=>y.length?`
        <div class="field-group">
          <div class="field-label">${me(g)}</div>
          <div class="chips">
            ${y.map(M=>`
              <button
                class="chip ${String(T??"").toLowerCase()===String(M.value??"").toLowerCase()?"active":""}"
                data-field="${me(R)}"
                data-value="${me(M.value)}"
              >${me(M.label)}</button>
            `).join("")}
          </div>
        </div>
      `:"",b=()=>`
      <div class="field-group">
        <div class="field-label">Passes</div>
        <div class="chips">
          <button class="chip ${o.clean_passes===1?"active":""}" data-field="clean_passes" data-value="1">1 Pass</button>
          <button class="chip ${o.clean_passes===2?"active":""}" data-field="clean_passes" data-value="2">2 Passes</button>
        </div>
      </div>
    `,w=()=>f?`
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
          <span class="room-name">${me(a)}</span>
          ${l?'<span class="dirty-badge">Unsaved</span>':""}
        </div>

        ${s?'<div class="carpet-notice">\u{1FAB5} Carpet room \u2014 mop fields hidden</div>':""}

        <div class="fields">
          ${h("Cleaning Mode","clean_mode",u,o.clean_mode)}
          ${h("Suction Level","fan_speed",m,o.fan_speed)}
          ${p.length?h("Water Level","water_level",p,o.water_level):""}
          ${h("Cleaning Path","clean_intensity",v,o.clean_intensity)}
          ${b()}
          ${w()}
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
    `;let S=this.shadowRoot.querySelector(".header");S.addEventListener("click",()=>this._handleToggle()),S.addEventListener("keydown",g=>{(g.key==="Enter"||g.key===" ")&&(g.preventDefault(),this._handleToggle())}),this.shadowRoot.querySelectorAll(".chip").forEach(g=>{g.addEventListener("click",()=>{let{field:R,value:y}=g.dataset,T=y;R==="clean_passes"&&(T=Number(y)),R==="edge_mopping"&&(T=y==="true"),this._setField(R,T)})}),this.shadowRoot.getElementById("save-btn")?.addEventListener("click",()=>this._handleSave()),this.shadowRoot.getElementById("start-btn")?.addEventListener("click",()=>this._handleStart())}async _handleToggle(){if(!this._hass)return;let e=this._targetSwitch(),t=this._allRoomSwitches(),r=e?.state==="on";await Promise.all(t.filter(a=>a.state==="on").map(a=>this._hass.callService("switch","turn_off",{entity_id:a.entityId}))),!r&&e&&await this._hass.callService("switch","turn_on",{entity_id:e.entityId})}async _selectExclusive(){let e=this._targetSwitch(),t=this._allRoomSwitches();await Promise.all(t.filter(r=>r.state==="on").map(r=>this._hass.callService("switch","turn_off",{entity_id:r.entityId}))),e&&await this._hass.callService("switch","turn_on",{entity_id:e.entityId})}async _handleSave(){if(this._saving||!this._hass||!this._fields)return;let e=this._targetSwitch();if(e){this._saving=!0,this._render();try{await this._hass.callService("eufy_vacuum","update_room_fields",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id),room_id:this._config.room_id,...this._fields}),this._fields=null}finally{this._saving=!1,this._render()}}}async _handleStart(){if(this._starting||!this._hass)return;let e=this._targetSwitch();if(e){this._starting=!0,this._render();try{this._isDirty()&&(await this._hass.callService("eufy_vacuum","update_room_fields",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id),room_id:this._config.room_id,...this._fields}),this._fields=null),await this._selectExclusive(),await this._hass.callService("eufy_vacuum","start_selected_rooms",{vacuum_entity_id:this._config.vacuum_entity_id,map_id:String(e.attrs.map_id)})}finally{this._starting=!1,this._render()}}}static getConfigElement(){return document.createElement(Nt)}static getStubConfig(e){let t=e?.states??{},r=Object.keys(t).find(c=>c.startsWith("vacuum."))??"",a=Object.entries(t).find(([c,n])=>c.startsWith("switch.")&&n.attributes?.vacuum_entity_id===r&&n.attributes?.room_id!=null);return{vacuum_entity_id:r,room_id:a?.[1]?.attributes?.room_id??null}}};function me(i){return String(i??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}customElements.define(Mc,Pt);window.customCards=window.customCards||[];window.customCards.push({type:Mc,name:"Eufy Room Card",description:"Single-room settings and quick-start card for managed vacuums."});
