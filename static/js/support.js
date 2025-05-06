function loadOrders() {
    $.get('/get_orders', function(data) {
        $('#support-table').DataTable({
            destroy: true,
            data: data,
            columns: [
                { data: 'id' },
                { data: 'order_number' },
                { data: 'item_name' },
                { data: 'billing_name' },
                { data: 'billing_phone' },
                { data: 'billing_street' },
                { data: 'billing_city' },
                {
                    data: 'status',
                    render: function (data, type, row) {
                        return `
                            <select class="status-select form-control form-select-sm" data-id="${row.id}">
                                <option ${data === 'Confirmed' ? 'selected' : ''}>Confirmed</option>
                                <option ${data === 'Pending' ? 'selected' : ''}>Pending</option>
                                <option ${data === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
                                <option ${data === 'Not Responding' ? 'selected' : ''}>Not Responding</option>
                                <option ${data === 'To Process' ? 'selected' : ''}>To Process</option>
                            </select>
                        `;
                    }
                }
            ],
            orderCellsTop: true,
            fixedHeader: true,
            initComplete: function () {
                let api = this.api();
                api.columns().every(function (index) {
                    const header = $('thead tr.filters th').eq(index);

                    if (index === 7) {
                        const select = $('<select class="form-control form-select-sm status-filter"><option value="">All</option></select>')
                            .appendTo(header.empty())
                            .on('change', function () {
                                api.column(index).search(this.value).draw();
                            });

                        this.data().unique().sort().each(function (d) {
                            if (d) select.append(`<option value="${d}">${d}</option>`);
                        });

                        select.select2({
                            placeholder: 'Search status',
                            width: '100%',
                            minimumResultsForSearch: Infinity
                        });
                    } else {
                        const input = header.find('input');
                        if (input.length) {
                            input.on('keyup change', function () {
                                api.column(index).search(this.value).draw();
                            });
                        }
                    }
                });

                // Initialize select2 on status columns
                $('.status-select').select2({
                    minimumResultsForSearch: -1,
                    width: '100%',
                    dropdownAutoWidth: true
                });
            }
        });
    });
}

$(document).ready(function() {
    loadOrders();

    $(document).on('change', '.status-select', function () {
        let select = $(this);
        let id = select.data('id');
        let newStatus = select.val();

        $.ajax({
            url: `/order/${id}/status`,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({ status: newStatus }),
            success: () => {
                select.addClass('border-success');
                setTimeout(() => select.removeClass('border-success'), 1000);
            },
            error: () => {
                select.addClass('border-danger');
                setTimeout(() => select.removeClass('border-danger'), 1000);
            }
        });
    });

    $(document).on('select2:opening', '.status-select', function (e) {
        $('.status-select').not(this).each(function () {
            if ($(this).data('select2')) {
                $(this).select2('close');
            }
        });
    });
});
