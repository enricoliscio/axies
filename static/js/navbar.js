var csrf_token = $('meta[name=csrf-token]').attr('content')

$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
            xhr.setRequestHeader("X-CSRFToken", csrf_token)
        }
    }
})

jQuery("#context-menu li").click(function (e) {
    $.ajax('/set_context', {
        type: 'POST',
        data: JSON.stringify({context_id: $(this).attr("id"), context_name: $(this).text()}),
        dataType: "json",
        contentType: "application/json",
        success: function (result) {
            $('#context-dropdown').html(result.context_name + '<span class="caret"></span>');
            window.location.reload(true);
        }
    });
});