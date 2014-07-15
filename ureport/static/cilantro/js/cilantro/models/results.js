define(["underscore","../core","../constants","../structs","./paginator"],function(t,e,i,n,s){var o=n.Frame.extend({idAttribute:"page_num",url:function(){var i=t.result(this.collection,"url");return e.utils.alterUrlParams(i,{page:this.id,per_page:this.collection.perPage})}}),r=n.FrameArray.extend({initialize:function(){t.bindAll(this,"fetch","markAsDirty","onWorkspaceUnload","onWorkspaceLoad","refresh"),this.isDirty=!0,this.isWorkspaceOpen=!1,this._refresh=t.debounce(this.refresh,i.CLICK_DELAY),e.on(e.VIEW_SYNCED,this.markAsDirty),e.on(e.CONTEXT_SYNCED,this.markAsDirty),this.on("workspace:load",this.onWorkspaceLoad),this.on("workspace:unload",this.onWorkspaceUnload)},onWorkspaceLoad:function(){this.isWorkspaceOpen=!0,this._refresh()},onWorkspaceUnload:function(){this.isWorkspaceOpen=!1},markAsDirty:function(){this.isDirty=!0,this._refresh()},fetch:function(t){t||(t={});var i;if((i=e.config.get("session.defaults.data.preview"))&&(t.type="POST",t.contentType="application/json",t.data=JSON.stringify(i)),this.isDirty&&this.isWorkspaceOpen)return this.isDirty=!1,void 0===t.cache&&(t.cache=!1),n.FrameArray.prototype.fetch.call(this,t);var s=this;return{done:function(){return delete s.pending}}}});return t.extend(r.prototype,s.PaginatorMixin),r.prototype.getPage=function(t,i){if(i||(i={}),this.hasPage(t)){var n=this.get(t);if(!n&&i.load!==!1){n=new this.model({page_num:t}),n.pending=!0,this.add(n);var s,o={};(s=e.config.get("session.defaults.data.preview"))&&(o.type="POST",o.contentType="application/json",o.data=JSON.stringify(s)),n.fetch(o).done(function(){delete n.pending})}return n&&i.active!==!1&&this.setCurrentPage(t),n}},r.prototype.model=o,{Results:r}});
//@ sourceMappingURL=results.js.map