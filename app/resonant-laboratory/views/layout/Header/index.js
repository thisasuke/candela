import d3 from 'd3';
import jQuery from 'jquery';
import Underscore from 'underscore';
import Backbone from 'backbone';
import myTemplate from './template.html';

import loadingIcon from '../../../images/spinner.gif';

import infoIcon from '../../../images/info.svg';
import newInfoIcon from '../../../images/newInfo.svg';

import datasetIcon from '../../../images/dataset.svg';
import matchingIcon from '../../../images/matching.svg';
import visualizationIcon from '../../../images/scatterplot.svg';

import addDatasetIcon from '../../../images/addDataset.svg';
import addVisualizationIcon from '../../../images/addVisualization.svg';

import publicIcon from '../../../images/public.svg';
import privateIcon from '../../../images/private.svg';
import libraryIcon from '../../../images/library.svg';
import scratchSpaceIcon from '../../../images/scratchSpace.svg';

let ICONS = {
  'DatasetView': datasetIcon,
  'MatchingView': matchingIcon,
  'VisualizationView': visualizationIcon,
  'AddDataset': addDatasetIcon,
  'AddVisualization': addVisualizationIcon,
  'PublicUser': publicIcon,
  'PrivateUser': privateIcon,
  'PublicLibrary': libraryIcon,
  'PublicScratch': scratchSpaceIcon
};

import './header.css';

let Header = Backbone.View.extend({
  addListeners: function () {
    this.listenTo(window.mainPage.currentUser, 'rl:logout', this.render);
    this.listenTo(window.mainPage.currentUser, 'rl:login', this.render);

    this.listenTo(window.mainPage, 'rl:changeProject',
      this.newProjectResponse);

    this.listenTo(window.mainPage.widgetPanels, 'rl:updateWidgetSpecs',
      this.render);

    this.listenTo(window.mainPage.currentUser.preferences,
      'rl:observeTips', this.render);
    this.listenTo(window.mainPage.currentUser.preferences,
      'rl:levelUp', this.notifyLevelUp);
  },
  newProjectResponse: function () {
    if (window.mainPage.project) {
      this.listenTo(window.mainPage.project,
        'rl:changeDatasets', this.render);
      this.listenTo(window.mainPage.project,
        'rl:changeVisualizations', this.render);
      this.listenTo(window.mainPage.project,
        'rl:changeStatus', this.render);
      this.listenTo(window.mainPage.project,
        'rl:rename', this.render);
    }
    this.render();
  },
  getVisibleTips: function () {
    let tips = {
      '#hamburgerButton': 'Main Menu',
      '#helpButton': 'Show these tips. This is blue ' +
                     'when there are new tips that you haven\'t seen yet.'
    /*,
      '#achievementsButton': `
Your achievements. See what you've accomplished,
and what you still haven't tried.`*/
    };

    if (window.mainPage.project) {
      tips['#projectLocationButton'] =
        'See/change who can see the project you\'re working on';

      tips['#projectName'] = 'Rename this project';

      if (window.mainPage.project.getMeta('datasets').length === 0) {
        tips['img.AddDataset.headerButton'] =
          'Add a dataset to this project';
      } else {
        tips['img.DatasetView.headerButton'] =
          'See/change the datasets in this project';
      }

      tips['img.MatchingView.headerButton'] = 'Manage the connections between the datasets and the visualizations in this project';

      if (window.mainPage.project.getMeta('visualizations').length === 0) {
        tips['img.AddVisualization.headerButton'] =
          'Add a visualization to this project';
      } else {
        tips['img.VisualizationView.headerButton'] =
          'Explore the visualizations in this project';
      }
    }

    return tips;
  },
  render: Underscore.debounce(function () {
    if (!this.templateAdded) {
      // Add the template and wire up all the default
      // button events
      this.$el.html(myTemplate);
      jQuery('#hamburgerButton').on('click', () => {
        window.mainPage.overlay.render('HamburgerMenu');
      });
      jQuery('#achievementsButton').on('click', () => {
        window.mainPage.overlay.render('AchievementLibrary');
      });
      jQuery('#helpButton').on('click', () => {
        window.mainPage.helpLayer.setTips(this.getVisibleTips());
        window.mainPage.helpLayer.show();
      });
      jQuery('#projectLocationButton')
        .on('click', () => {
          window.mainPage.overlay.render('ProjectSettings');
        });
      jQuery('#projectName').on('focus', function () {
        // this refers to the DOM element
        this.value = this.textContent;
        // We patch on .value to the element to pretend it's
        // a real input (contenteditable stretches better)
      });
      jQuery('#projectName').on('blur', function () {
        // this refers to the DOM element
        if (this.value !== this.textContent) {
          if (this.textContent.length === 0) {
            this.textContent = this.value;
          } else {
            this.value = this.textContent;
            window.mainPage.project.rename(this.textContent);
          }
        }
      });
      jQuery('#projectName').on('keydown', function (event) {
        // this refers to the DOM element
        let key = event.keyCode || event.charCode;
        if (key === 13 || key === 27) {
          jQuery(this).blur();
          // Workaround for webkit's bug
          window.getSelection().removeAllRanges();
        }
      });
      this.templateAdded = true;
    }

    // TODO: don't check for tips that won't be visible
    // (e.g. add/remove datasets, visualizations)
    let tips = this.getVisibleTips();
    if (window.mainPage.currentUser.preferences
        .hasSeenAllTips(tips)) {
      jQuery('#helpButton').attr('src', infoIcon);
    } else {
      jQuery('#helpButton').attr('src', newInfoIcon);
    }

    if (window.mainPage.project) {
      // Render information about the project
      jQuery('#projectHeader, #projectIcons').show();

      let projectStatus = window.mainPage.project.status;
      if (projectStatus.location === null) {
        jQuery('#projectLocationButton')
          .attr('src', loadingIcon);
      } else {
        jQuery('#projectLocationButton')
          .attr('src', ICONS[projectStatus.location]);
      }

      jQuery('#projectName').text(window.mainPage.project.get('name'));

      // Set up all the widget icons
      let widgetIcons = window.mainPage.project.getAllWidgetSpecs();

      // Prepend and append the buttons for adding stuff
      // (TODO: *always* include these when multiple datasets /
      // multiple visualizations are supported)
      if (window.mainPage.project.getMeta('datasets').length === 0) {
        widgetIcons.unshift({
          widgetType: 'AddDataset'
        });
      }
      if (window.mainPage.project.getMeta('visualizations').length === 0) {
        widgetIcons.push({
          widgetType: 'AddVisualization'
        });
      }

      let widgetButtons = d3.select(this.el).select('#projectIcons')
        .selectAll('img.headerButton').data(widgetIcons);
      widgetButtons.enter().append('img')
        .attr('class', (d) => {
          return d.widgetType + ' headerButton';
        });
      widgetButtons.exit().remove();
      widgetButtons.attr('src', (d) => {
        return ICONS[d.widgetType];
      }).attr('title', d => {
        return tips['img.' + d.widgetType + '.headerButton'];
      }).on('click', (d) => {
        if (d.widgetType === 'AddDataset') {
          window.mainPage.overlay.render('DatasetLibrary');
        } else if (d.widgetType === 'AddVisualization') {
          window.mainPage.overlay.render('VisualizationLibrary');
        } else {
          window.mainPage.widgetPanels.toggleWidget(d, true);
        }
      });
    } else {
      // We're in an empty state with no project loaded
      // (an overlay should be showing, so don't sweat the toolbar)
      jQuery('#projectHeader, #projectIcons').hide();
    }
  }, 300),
  notifyLevelUp: function () {
    // TODO
    console.log('level up!');
  }
});

export default Header;
