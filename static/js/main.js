/**
 * Call to Flask to get all values submitted by the current user. Adds a new keyword if a click
 * event was recorded.
 * @param  {boolean} reload=false - if true, the page was reloaded, and no value should be added
 */
function getValues(reload=false, show_skip=true) {
  var new_value = ""
  if (!reload) {
    new_value = $('input[name="value"]').val();
  }
  $.getJSON($SCRIPT_ROOT + '/add_value', {
    value: new_value
  }, function(data) {
    $("#value-list").empty();
    for (x in data.result) {
      if (0 !== data.result[x].name.length) {
        var value_id = data.result[x].id;

        var skip_motivation_button = "";
        if (show_skip) {
          skip_motivation_button = `<div class="col-sm-5">
              <button class="btn similar-motivations-button" id="${value_id}" disabled="true">
              Next (Similar) Motivation <span class="glyphicon glyphicon-forward"></span>
              </button>
            </div>`
        }
        $("#value-list").append(
          ` <li class="list-group-item">
              <div class="row">
                <div class="col-sm-7">
                  <h3 style='display:inline-block'>
                    ${data.result[x].name}
                    <span class="glyphicon glyphicon-remove remove_value remove-entry-icon" id="${value_id}"></span>
                  </h3>
                </div>
                ${skip_motivation_button}
              </div>
              <ul class="list-inline list-group-horizontal-sm" id='keyword-list${value_id}'>
              </ul>
              <br/>
              <div class="row">
                <div class="col-sm-12 form-group">
                  <div class="col-sm-8">
                    <form class="form-inline" action="javascript:void(0);">
                    <input class="form-control" placeholder="Enter a new keyword" type=text name="keyword_add${value_id}">
                    <input class="btn btn-default add_keyword" type="button" style="cursor: pointer" id="${value_id}" value="Add keyword">
                    </form>
                  </div>
                  <div class="col-sm-4">
                    <p class="form-control-static" id="keyword-suggestions${value_id}">
                    </p>
                  </div>
                </div>
              </div>
            </li>`
        );
        getKeywords(event=undefined, valud_id=value_id, trigger=false);
        if (value_id === data.suggestions.id) {
          $('#keyword-suggestions'+value_id).text("Similar terms: " + data.suggestions.text);
        }
      }
    }
    $('input[name="value"]').val('');
    if (!data.changed) {
      $(document).trigger("annotation_update", [{prevent_button_update: true}]);
    } else {
      $(document).trigger("annotation_update", [{prevent_button_update: false}]);
    }
  });
  return false;
}


/**
 * Call to flask to get all keywords associated with the value_id. Adds a new keyword if a click
 * event was recorded.
 *
 * @param  {PlainObject} event=undefined - if set, contains the click event of the keyword addition
 * @param  {number} value_id=-1 - if not set to -1, contains the value_id of the keyword list to be updated
 * @param  {boolean} trigger=true - if true, trigger the annotation_update event
 * @param  {string} append_prefix="" - if not the empty string, add this prefix in front of the id used for
 *                                     locating the list of keywords.
 */
function getKeywords(event=undefined, value_id=-1, trigger=true, append_prefix="") {
  if (value_id === -1 && event != undefined) {
    value_id = $(event.currentTarget).attr('id');
  }
  keyword_name = $('input[name=\"keyword_add'+value_id+'\"]').val();
  $.getJSON($SCRIPT_ROOT + '/add_keyword', {
    keyword_name: keyword_name,
    value_id: value_id
  }, function(data) {
    $("#keyword-list" +value_id).empty();
    for (x in data.result) {
      if (0 !== data.result[x].name.length) {
        $("#" + append_prefix + "keyword-list" +value_id).append(
          ` <li class="text-center list-group-item"> ${data.result[x].name}
              <span class="glyphicon glyphicon-remove remove_keyword remove-entry-icon" id="${data.result[x].id}" ></span>
            </li>`
        );
      }
      if (value_id == data.suggestions.id) {
        $('#keyword-suggestions'+value_id).text("Similar terms: " + data.suggestions.text);
      }
    }
    $('input[name="keyword_add' + value_id + '"]').val('');
    if (trigger) {
      if (!data.changed) {
        $(document).trigger("annotation_update", [{prevent_button_update: true}]);
      } else {
        $(document).trigger("annotation_update", [{prevent_button_update: false}]);
      }
    }
  });
  return false;
}


/**
 * Remove a value, and all keywords related to the value from the database by its id.
 *
 * @param  {number} value_id - value id to remove from database
 */
function removeValue(value_id) {
  var element = $(this);
  $.getJSON($SCRIPT_ROOT + '/remove_value', {
    value_id: $(this).attr('id'),
  }, function(data) {
    if (data.success === true) {
      element.closest('li').remove();
    }
    $(document).trigger("annotation_update");
  });
}


/**
 * Remove a keyword from the database by its id.
 *
 * @param  {number} keyword_id - keyword id to remove from database
 */
function removeKeyword(keyword_id) {
  var element = $(this);
  $.getJSON($SCRIPT_ROOT + '/remove_keyword', {
    keyword_id: $(this).attr('id'),
  }, function(data) {
    if (data.success === true) {
      element.closest('li').remove();
    }
    $(document).trigger("annotation_update");
  });
}

/**
 * Show a new motivation, this one being similar to the provided value.
 * @param  {event} event=undefined - button click event.
 * @param  {number} value_id=-1 - value id to show similar motivation to.
 */
function showSimilarMotivation(event=undefined, value_id=-1) {
  if (event != undefined) {
    var value_id = $(event.currentTarget).attr('id');
    $.getJSON($SCRIPT_ROOT + '/preload_next', {
      value_id: value_id,
    }, function(data) {
      if (data.success === true) {
        window.location.reload();
      }
    });
  }
}

/**
 * Skip a motivation with a specific reason
 *
 * @param  {number} reason_id - reason ID to skip the motivation:
 * {
 *  1: Motivation is uncomprehensible
 *  2: No value can be extracted from the motivation
 *  3: The value and keywords for the motivations are already present
 * }
 */
function skipMotivation(reason_id) {
  $.getJSON($SCRIPT_ROOT + '/skip_motivation', {
    skip_reason: reason_id,
  }, function(data) {
    $(document).trigger("annotation_update");
    $("input").prop("disabled", true);
    $(".remove-entry-icon").remove();
    $('input[name="value"]').val("");
  });
}

/**
 * Turn ON the button for next motivation.
 * Turn OFF the buttons for skipping the current one.
 */
function switchButtons() {
  $('#skip-uncomprehensible').prop('disabled', true);
  $('#skip-no-value').prop('disabled', true);
  $('#skip-already-present').prop('disabled', true);
  $('#next-motivation').prop('disabled', false);
  $(".similar-motivations-button").prop("disabled", false);
}


// Helper function for drawing
function getLabelLocation(index, columns=3) {
  var cols = [125, 325, 625];
  var rows = [720, 750, 780, 810];
  col_idx = index % columns;
  row_idx = Math.floor(index/columns);
  var dd = {x: cols[col_idx], y: rows[row_idx]};
  return dd;
}
/**
 * Draw the user action history plot using D3.js.
 */
function drawHistory() {
  var margin = {top: 50, right: 0, bottom: 200, left: 70};
  var width = 640;
  var height = width;
  // Keys of the legend, same order as color_map in app/utils/backbone/utils.py
  var keys = [
    "Value addition",
    "Keyword addition",
    "Multiple additions",
    "Value removal",
    "Keyword removal",
    "Multiple removals",
    "Multiple additions and removals",
    "Value already annotated",
    "No value or not comprehensible motivation",
    "Read motivation similar to value"
  ];
  // Colors of the legend keys, as per color_map in app/utils/backbone/utils.py
  var legend_colors = [
    '#31a354',  // Dark green
    '#a1d99b',  // Light green
    '#74c476',  // Green
    '#e6550d',  // Dark red
    '#fdae6b',  // Light red
    '#fd8d3c',  // Red
    '#9e9ac8',  // Purple
    '#3182bd',  // Dark blue
    '#6baed6',  // Blue
    '#969696'   // Gray
  ];

  $.getJSON($SCRIPT_ROOT + '/get_history', {
  }, function(data) {
    // Check if there is data in the history other than null
    var otherThanNull = data['history'].some(function (el) {
      return el !== null;
    });
    if (!otherThanNull) {
      return;
    }

    d3.select('#history-plot').remove();
    // Prase data to more suitable format
    var x_data = data['history'][0];
    var y_data = data['history'][1];
    var colors = data['history'][2];
    var zipped_data = x_data.map(function(_, i) {
      return [x_data[i], y_data[i], colors[i]];
    });

    // Set scales
    var x = d3.scaleBand()
      .range([0, width])
      .domain(d3.range(x_data.length))
      .rangeRound([0, width])
      .paddingInner(0.1)
      .paddingOuter(0.1);
    var y = d3.scaleLinear()
      .range([height, 0])
      .domain([0, d3.max(y_data)]);

    // Insert SVG
    var svg = d3.select("div#chartArea")
      .append("div")
      .classed("svg-container", true)
      .append("svg")
      .attr('id', 'history-plot')
      .attr("preserveAspectRatio", "xMinYMin meet")
      .attr("viewBox", -1 * margin.left + " "+ (-1 * margin.top) + " " + (width + margin.left) + " " + (height + margin.bottom + margin.top))
      .classed("svg-content-responsive", true)

    // Append the rectangles for the bar chart
    svg.selectAll(".bar")
      .data(zipped_data)
        .enter().append("rect")
          .attr("class", "bar")
          .attr("x",      function(d) { return x(d[0])})
          .attr("width",  function(d) { return x.bandwidth() })
          .attr("y",      function(d) { return y(d[1]); })
          .attr("height", function(d) { return height - y(d[1]); })
          .attr('fill',   function(d) { return d[2]});

    var ticks = x.domain().filter(function(d,i){ return !(i%5); } );
    // Add the x Axis
    svg.append("g")
      .attr("transform", "translate(0," + height + ")")
      .attr('id', 'x-axis-ticks')
      .call(d3.axisBottom(x).tickValues(ticks));
    // Add x label
    svg.append("text")
      .attr('id', 'x-axis-label')
      .attr("transform", "translate(" + (width/2) + " ," + (height + 50) + ")")
      .style("text-anchor", "middle")
      .text("Read motivations");

    // Add the y Axis
    svg.append("g")
      .attr('id', 'y-axis-ticks')
      .call(d3.axisLeft(y));
    // Add y label
    svg.append("text")
      .attr('id', 'y-axis-label')
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - (height / 2))
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .text("Difference");

      // Prepare keys for legend
    var label_size = 8;
    var legend_cols = 3;
    svg.selectAll("dots")
      .data(keys)
      .enter()
      .append("circle")
        .attr("cx", function(d,i){ return getLabelLocation(i, columns=legend_cols).x; })
        .attr("cy", function(d,i){ return getLabelLocation(i, columns=legend_cols).y; })
        .attr("r", label_size)
        .style("fill", function(d, i){ return legend_colors[i]});

    // Also add labels
    svg.selectAll("labels")
      .data(keys)
      .enter()
      .append("text")
        .attr("x", function(d,i){ return getLabelLocation(i, columns=legend_cols).x-15; })
        .attr("y", function(d,i){ return getLabelLocation(i, columns=legend_cols).y + label_size/2; })
        .style("fill", function(d, i){ return legend_colors[i]})
        .style("font-size", '1.2rem')
        .text(function(d){ return d})
        .attr("text-anchor", "end")


  });
}
