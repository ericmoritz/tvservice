/**
 * Transform text into a URL slug: spaces turned into dashes, remove
 /**non alnum
 * @param string text
 */
function slugify(text) {
  text = text.replace(/[^-a-zA-Z0-9,&\s]+/ig, '');
  text = text.replace(/-/gi, "_");
  text = text.replace(/\s/gi, "-");
  return text.toLowerCase();
}

function activePage() {
  return $(".ui-page-active");
}

function reapplyStyles(el) {
  el.find('ul[data-role]').listview();
  el.find('div[data-role="fieldcontain"]').fieldcontain();
  el.find('button[data-role="button"]').button();
  el.find('input,textarea').textinput();
  return el.page();
}

var Show = Backbone.Model.extend({
  url: function() {
    return "/shows/" + this.get("slug");
  }

});

var Shows = Backbone.Collection.extend({
  url: '/shows/',
  model: Show,
  parse: function(response) {
    return _.map(response, function(title, slug) {
      return {"id": slug, "slug": slug, "title": title};
    });
  }
});

var AddShowView = Backbone.View.extend({
  el: $("#add-show-form"),
  events: {
    "click #add-show-btn": "addShow",
    "keypress #show-name": "updateOnEnter"
  },
  initialize: function(options) {
    this.input = this.$("#show-name");
    this.coll = options.collection;
    
    _.bindAll(this);
  },
  updateOnEnter: function(e) {
    if (e.keyCode == 13) {
      this.addShow();
    }
  },
  addShow: function() {
    var title = this.input.val();
    this.input.val("");
    if(title.length > "") {
      var slug = slugify(title);
      var data = {"id": slug,
                  "slug": slug,
                  "title": title}
      this.coll.create(data);
    }
  }
});

var ShowListView = Backbone.View.extend({
  el: $("#shows-view"),

  initialize: function(options) {
    this.coll = options.collection;

    this.coll.bind("add",   this.addOne, this);
    this.coll.bind("reset", this.addAll, this);
    this.coll.bind("all",   this.render, this);
    _.bindAll(this);
  },

  addOne: function(show) {
    var view = new ShowListItemView({model: show});
    this.el.append(view.render().el);
  },

  addAll: function() {
    this.coll.each(this.addOne);
  },

  render: function() {
    $(this.el).listview("refresh");
    return this;
  }
});

var ShowListItemView = Backbone.View.extend({
  tagName: "li",
  template: _.template($("#show-item-template").html()),
  events: {
    "click .delete": "delete_model"
  },

  initialize: function() {},

  render: function() {
    $(this.el).html(this.template(this.model.toJSON()));
    this.$("input").textinput();
    this.$("button").button();
    return this;
  },
  delete_model: function() {
    if(confirm("Are you sure?")) {
      this.model.destroy();
      $(this.el).remove();
    }
  }
});

var HomeView = Backbone.View.extend({
  initialize: function(options) {
    // Collections
    this.collections = {};
    this.collections.shows = options.shows

    // Views
    this.views = {};
    this.views.showsListView = new ShowListView({collection: this.collections.shows});
    this.views.addShowView = new AddShowView({collection: this.collections.shows});

    // Fetch the current list of shows
    this.collections.shows.fetch();
  }

});

var Home = Backbone.View.extend({
  initialize: function(options) {
    this.shows = options.shows;
    this.views = {}
    this.views.home = new HomeView({shows:this.shows});

    _.bindAll(this);
  }
});


var App = Backbone.Router.extend({
  routes: {
    "home": "home"
  },
  initialize: function(options) {
    this.shows = new Shows();
    this.views = {}
    this.views.home = new HomeView({shows:this.shows});
    Backbone.history.start()
  }, 
  home: function() {
    return this.views.home;
  },
})

app = new App();
app.home();
